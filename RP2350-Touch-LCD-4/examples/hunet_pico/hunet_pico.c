#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/irq.h"
#include "hardware/clocks.h"
#include "bsp_i2c.h"
#include "../lvgl/lv_port/lv_port_disp.h"
#include "../lvgl/lv_port/lv_port_indev.h"

// ── UART1 behind the onboard RS485 port ─────────────────
// External connector: RP2350 RS485 A/B.
// Pico side requires a separate TTL-to-RS485 module:
// Pico GP4(TX) -> module DI -> A/B -> RP2350 RS485 A/B
// Pico GP5(RX) <- module RO <- A/B <- RP2350 RS485 A/B
#define PICO_UART       uart1
#define PICO_UART_TX    8
#define PICO_UART_RX    9
#define PICO_UART_BAUD  115200

// ── I2C1 (GP6/GP7) → bsp_i2c_init() 터치 전용으로 해방 ──

#define LVGL_TICK_MS 10

// ── UART 수신 버퍼 ────────────────────────────────────
static char          rx_buf[128];
static volatile int  rx_len     = 0;
static volatile bool data_ready = false;

// ── 릴레이 명령 (터치로 토글, UART로 Pico에 전송) ──────
static volatile uint8_t g_relay_cmd = 0;  // 0=OFF, 1=ON

// ── 센서 데이터 ───────────────────────────────────────
typedef struct {
    float air_temp, humidity, moisture, soil_temp, ph;
    int   ec, n, p, k, solar, co2;
} SensorData;
static SensorData g_sensor = {0};

// ── LVGL 핸들 ─────────────────────────────────────────
static lv_obj_t *val_air_temp, *val_humidity, *val_solar;
static lv_obj_t *val_moisture, *val_soil_temp, *val_co2;
static lv_obj_t *val_ec,       *val_ph;
static lv_obj_t *val_n,        *val_p,         *val_k;
static lv_obj_t *val_relay;
static lv_obj_t *relay_card;
static lv_obj_t *lbl_status;

// ── UART1 RX IRQ ──────────────────────────────────────
static void uart_rx_irq_handler(void) {
    while (uart_is_readable(PICO_UART)) {
        char c = uart_getc(PICO_UART);
        
        // '?' is a short poll request for the relay command
        if (c == '?') {
            uart_putc_raw(PICO_UART, g_relay_cmd);
            continue;
        }

        if (rx_len < (int)(sizeof(rx_buf) - 1)) {
            rx_buf[rx_len++] = c;
            if (c == '\n') {
                rx_buf[rx_len] = '\0';
                data_ready = true;
                // Full CSV received: respond with relay command
                uart_putc_raw(PICO_UART, g_relay_cmd);
                rx_len = 0;
            }
        } else {
            rx_len = 0;
        }
    }
}

static void uart_pico_setup(void) {
    uart_init(PICO_UART, PICO_UART_BAUD);
    gpio_set_function(PICO_UART_TX, GPIO_FUNC_UART);
    gpio_set_function(PICO_UART_RX, GPIO_FUNC_UART);

    irq_set_exclusive_handler(UART1_IRQ, uart_rx_irq_handler);
    irq_set_enabled(UART1_IRQ, true);
    uart_set_irq_enables(PICO_UART, true, false);  // RX IRQ only
}

// ── CSV 파싱 ──────────────────────────────────────────
// 포맷: air_temp,humidity,moisture,soil_temp,ec,ph,n,p,k,solar,co2,relay\n
static bool parse_csv(const char *s, SensorData *d) {
    float v[12] = {0};
    int n = sscanf(s, "%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f",
                   &v[0],&v[1],&v[2],&v[3],&v[4],&v[5],
                   &v[6],&v[7],&v[8],&v[9],&v[10],&v[11]);
    if (n < 11) return false;
    d->air_temp  = v[0];  d->humidity  = v[1];
    d->moisture  = v[2];  d->soil_temp = v[3];
    d->ec        = (int)v[4];  d->ph   = v[5];
    d->n         = (int)v[6];  d->p    = (int)v[7];
    d->k         = (int)v[8];  d->solar = (int)v[9];
    d->co2       = (int)v[10];
    return true;
}

// ── 릴레이 UI 업데이트 ────────────────────────────────
static void update_relay_ui(void) {
    if (g_relay_cmd) {
        lv_label_set_text(val_relay, "ON");
        lv_obj_set_style_text_color(val_relay, lv_color_hex(0x10b981), 0);
        lv_obj_set_style_bg_color(relay_card, lv_color_hex(0x134e4a), 0);
        lv_obj_set_style_border_color(relay_card, lv_color_hex(0x10b981), 0);
    } else {
        lv_label_set_text(val_relay, "OFF");
        lv_obj_set_style_text_color(val_relay, lv_color_hex(0x64748b), 0);
        lv_obj_set_style_bg_color(relay_card, lv_color_hex(0x1e293b), 0);
        lv_obj_set_style_border_color(relay_card, lv_color_hex(0x334155), 0);
    }
}

// ── 릴레이 터치 콜백 ──────────────────────────────────
static void relay_touch_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        g_relay_cmd ^= 1;
        update_relay_ui();
    }
}

// ── 카드 생성 ─────────────────────────────────────────
static lv_obj_t *make_card(lv_obj_t *parent,
                            const char *title,
                            uint32_t accent,
                            lv_obj_t **out_val) {
    lv_obj_t *card = lv_obj_create(parent);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x1e293b), 0);
    lv_obj_set_style_border_color(card, lv_color_hex(0x334155), 0);
    lv_obj_set_style_border_width(card, 1, 0);
    lv_obj_set_style_radius(card, 10, 0);
    lv_obj_set_style_pad_all(card, 10, 0);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(card, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);

    lv_obj_t *lbl = lv_label_create(card);
    lv_label_set_text(lbl, title);
    lv_obj_set_style_text_color(lbl, lv_color_hex(0x94a3b8), 0);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_12, 0);

    lv_obj_t *val = lv_label_create(card);
    lv_label_set_text(val, "--");
    lv_obj_set_style_text_color(val, lv_color_hex(accent), 0);
    lv_obj_set_style_text_font(val, &lv_font_montserrat_20, 0);
    lv_obj_set_style_pad_top(val, 4, 0);

    *out_val = val;
    return card;
}

// ── 대시보드 UI 생성 ──────────────────────────────────
static void create_dashboard(void) {
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0x0f172a), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

    // 헤더
    lv_obj_t *hdr = lv_obj_create(scr);
    lv_obj_set_size(hdr, 480, 44);
    lv_obj_set_pos(hdr, 0, 0);
    lv_obj_set_style_bg_color(hdr, lv_color_hex(0x1e293b), 0);
    lv_obj_set_style_border_width(hdr, 0, 0);
    lv_obj_set_style_radius(hdr, 0, 0);
    lv_obj_clear_flag(hdr, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = lv_label_create(hdr);
    lv_label_set_text(title, "Hunet Sensor Dashboard");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(title, lv_color_hex(0xf1f5f9), 0);
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 12, 0);

    lbl_status = lv_label_create(hdr);
    lv_label_set_text(lbl_status, "WAIT");
    lv_obj_set_style_text_font(lbl_status, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(lbl_status, lv_color_hex(0x64748b), 0);
    lv_obj_align(lbl_status, LV_ALIGN_RIGHT_MID, -12, 0);

    // 카드 그리드 (480×436, 3열 4행)
    lv_obj_t *grid = lv_obj_create(scr);
    lv_obj_set_size(grid, 480, 436);
    lv_obj_set_pos(grid, 0, 44);
    lv_obj_set_style_bg_color(grid, lv_color_hex(0x0f172a), 0);
    lv_obj_set_style_border_width(grid, 0, 0);
    lv_obj_set_style_radius(grid, 0, 0);
    lv_obj_set_style_pad_all(grid, 8, 0);
    lv_obj_set_style_pad_gap(grid, 8, 0);
    lv_obj_set_flex_flow(grid, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(grid, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_clear_flag(grid, LV_OBJ_FLAG_SCROLLABLE);

    int cw = (480 - 8*2 - 8*2) / 3;
    int ch = (436 - 8*2 - 8*3) / 4;

    lv_obj_t *c;
    // 행 0
    c = make_card(grid, "Air Temp",  0xfb923c, &val_air_temp);  lv_obj_set_size(c, cw, ch);
    c = make_card(grid, "Humidity",  0x38bdf8, &val_humidity);   lv_obj_set_size(c, cw, ch);
    c = make_card(grid, "Solar",     0xfacc15, &val_solar);      lv_obj_set_size(c, cw, ch);
    // 행 1
    c = make_card(grid, "Moisture",  0x34d399, &val_moisture);   lv_obj_set_size(c, cw, ch);
    c = make_card(grid, "Soil Temp", 0xfbbf24, &val_soil_temp);  lv_obj_set_size(c, cw, ch);
    c = make_card(grid, "CO2",       0x6ee7b7, &val_co2);        lv_obj_set_size(c, cw, ch);
    // 행 2
    c = make_card(grid, "EC",        0xa78bfa, &val_ec);         lv_obj_set_size(c, cw, ch);
    c = make_card(grid, "pH",        0xf472b6, &val_ph);         lv_obj_set_size(c, cw, ch);
    // 릴레이 카드 — 터치 ON/OFF
    relay_card = lv_obj_create(grid);
    lv_obj_set_size(relay_card, cw, ch);
    lv_obj_set_style_radius(relay_card, 10, 0);
    lv_obj_set_style_border_width(relay_card, 2, 0);
    lv_obj_set_style_pad_all(relay_card, 10, 0);
    lv_obj_clear_flag(relay_card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(relay_card, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(relay_card, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_add_flag(relay_card, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(relay_card, relay_touch_cb, LV_EVENT_CLICKED, NULL);

    lv_obj_t *relay_title = lv_label_create(relay_card);
    lv_label_set_text(relay_title, "Relay [TAP]");
    lv_obj_set_style_text_color(relay_title, lv_color_hex(0x94a3b8), 0);
    lv_obj_set_style_text_font(relay_title, &lv_font_montserrat_12, 0);

    val_relay = lv_label_create(relay_card);
    lv_obj_set_style_text_font(val_relay, &lv_font_montserrat_20, 0);
    lv_obj_set_style_pad_top(val_relay, 4, 0);
    update_relay_ui();

    // 행 3: NPK
    c = make_card(grid, "N", 0x4ade80, &val_n);  lv_obj_set_size(c, cw, ch);
    c = make_card(grid, "P", 0xf87171, &val_p);  lv_obj_set_size(c, cw, ch);
    c = make_card(grid, "K", 0x60a5fa, &val_k);  lv_obj_set_size(c, cw, ch);
}

// ── 레이블 업데이트 ───────────────────────────────────
static void update_labels(const SensorData *d) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%.1f C",    d->air_temp);  lv_label_set_text(val_air_temp,  buf);
    snprintf(buf, sizeof(buf), "%.1f %%",  d->humidity);  lv_label_set_text(val_humidity,   buf);
    snprintf(buf, sizeof(buf), "%d W/m2",  d->solar);     lv_label_set_text(val_solar,      buf);
    snprintf(buf, sizeof(buf), "%.1f %%",  d->moisture);  lv_label_set_text(val_moisture,  buf);
    snprintf(buf, sizeof(buf), "%.1f C",   d->soil_temp); lv_label_set_text(val_soil_temp, buf);
    snprintf(buf, sizeof(buf), "%d ppm",   d->co2);       lv_label_set_text(val_co2,       buf);
    snprintf(buf, sizeof(buf), "%d uS/cm", d->ec);        lv_label_set_text(val_ec,        buf);
    snprintf(buf, sizeof(buf), "%.1f",     d->ph);        lv_label_set_text(val_ph,        buf);
    snprintf(buf, sizeof(buf), "%d mg/kg", d->n);         lv_label_set_text(val_n,         buf);
    snprintf(buf, sizeof(buf), "%d mg/kg", d->p);         lv_label_set_text(val_p,         buf);
    snprintf(buf, sizeof(buf), "%d mg/kg", d->k);         lv_label_set_text(val_k,         buf);

    lv_label_set_text(lbl_status, "LIVE");
    lv_obj_set_style_text_color(lbl_status, lv_color_hex(0x10b981), 0);
}

static void set_cpu_clock(uint32_t mhz) {
    set_sys_clock_khz(mhz * 1000, true);
    clock_configure(clk_peri, 0,
        CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLKSRC_PLL_SYS,
        mhz * 1000 * 1000, mhz * 1000 * 1000);
}

static bool lvgl_tick_cb(struct repeating_timer *t) {
    lv_tick_inc(LVGL_TICK_MS);
    return true;
}

int main(void) {
    static struct repeating_timer lvgl_timer;
    stdio_init_all();
    sleep_ms(100);

    set_cpu_clock(260);
    uart_pico_setup();   // UART1 GP8/GP9 (Pico 데이터 수신)
    bsp_i2c_init();      // I2C1 GP6/GP7 (터치/IMU 전용)

    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();  // 터치 활성화
    add_repeating_timer_ms(LVGL_TICK_MS, lvgl_tick_cb, NULL, &lvgl_timer);

    create_dashboard();

    static char local_buf[128];
    while (true) {
        if (data_ready) {
            strncpy(local_buf, rx_buf, sizeof(local_buf));
            data_ready = false;
            if (parse_csv(local_buf, &g_sensor)) {
                update_labels(&g_sensor);
            }
        }
        lv_timer_handler();
        sleep_ms(LVGL_TICK_MS);
    }
}
