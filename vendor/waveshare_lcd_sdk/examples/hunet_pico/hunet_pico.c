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
#define PICO_UART       uart1
#define PICO_UART_TX    8
#define PICO_UART_RX    9
#define PICO_UART_BAUD  115200

#define LVGL_TICK_MS 10
#define HISTORY_SIZE 60  // 약 5~10분 정도의 흐름 표시
#define PUMP_RUN_MS 10000

// ── UART 수신 버퍼 ────────────────────────────────────
static char          rx_buf[128];
static volatile int  rx_len     = 0;
static volatile bool data_ready = false;

// ── 테마 설정 ─────────────────────────────────────────
static bool is_dark_mode = true;

// ── 릴레이 명령 (4채널 확장 대비) ────────────────────────
static volatile uint8_t g_relay_cmd[4] = {0, 0, 0, 0};  // 0=OFF, 1=ON

// ── 센서 데이터 및 히스토리 ──────────────────────────────
typedef struct {
    float air_temp, humidity, moisture, soil_temp, ph;
    int   ec, n, p, k, solar, co2;
} SensorData;
static SensorData g_sensor = {0};
static float      g_history[11][HISTORY_SIZE] = {0};

const char *sensor_names[] = {
    "Air Temp", "Humidity", "Solar",
    "Moisture", "Soil Temp", "CO2",
    "EC", "pH", "Nitrogen(N)",
    "Phosph(P)", "Potass(K)"
};

const char *sensor_units[] = {
    "C", "%", "W/m2",
    "%", "C", "ppm",
    "uS/cm", "", "mg/kg",
    "mg/kg", "mg/kg"
};

// ── LVGL 핸들 ─────────────────────────────────────────
static lv_obj_t *val_air_temp, *val_humidity, *val_solar;
static lv_obj_t *val_moisture, *val_soil_temp, *val_co2;
static lv_obj_t *val_ec,       *val_ph;
static lv_obj_t *val_n,        *val_p,         *val_k;
static lv_obj_t *val_sys_info;

static lv_obj_t *relay_cards[4];
static lv_obj_t *val_relays[4];
static lv_obj_t *lbl_relays[4];
static uint64_t pump_until_ms[4] = {0, 0, 0, 0};

// ── 그래프 팝업 관련 ────────────────────────────────────
static lv_obj_t *modal_bg = NULL;
static lv_chart_series_t *chart_ser = NULL;
static lv_obj_t *chart_obj = NULL;
static lv_obj_t *val_modal_curr = NULL;
static int       current_graph_sensor = -1;

// ── 함수 선언 ─────────────────────────────────────────
static void create_dashboard(void);
static void update_labels(const SensorData *d);

static uint8_t relay_mask(void) {
    uint8_t mask = 0;
    for (int i = 0; i < 4; i++) {
        if (g_relay_cmd[i]) mask |= (uint8_t)(1u << i);
    }
    return mask;
}

// ── UART1 RX IRQ ──────────────────────────────────────
static void uart_rx_irq_handler(void) {
    while (uart_is_readable(PICO_UART)) {
        char c = uart_getc(PICO_UART);
        if (c == '?') {
            uart_putc_raw(PICO_UART, relay_mask()); 
            continue;
        }
        if (rx_len < (int)(sizeof(rx_buf) - 1)) {
            rx_buf[rx_len++] = c;
            if (c == '\n') {
                rx_buf[rx_len] = '\0';
                data_ready = true;
                uart_putc_raw(PICO_UART, relay_mask());
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
    uart_set_irq_enables(PICO_UART, true, false);
}

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

static void update_relay_ui(int idx) {
    uint32_t active_bg = is_dark_mode ? 0x134e4a : 0xd1fae5;
    uint32_t active_border = 0x10b981;
    uint32_t inactive_bg = is_dark_mode ? 0x1e293b : 0xffffff;
    uint32_t inactive_border = is_dark_mode ? 0x334155 : 0xe2e8f0;

    if (g_relay_cmd[idx]) {
        if ((idx == 1 || idx == 2) && pump_until_ms[idx] > 0) {
            uint64_t now = to_ms_since_boot(get_absolute_time());
            int remain = (pump_until_ms[idx] > now) ? (int)((pump_until_ms[idx] - now + 999) / 1000) : 0;
            char buf[16];
            snprintf(buf, sizeof(buf), "%ds", remain);
            lv_label_set_text(val_relays[idx], buf);
        } else {
            lv_label_set_text(val_relays[idx], "ON");
        }
        lv_obj_set_style_text_color(val_relays[idx], lv_color_hex(0x10b981), 0);
        lv_obj_set_style_bg_color(relay_cards[idx], lv_color_hex(active_bg), 0);
        lv_obj_set_style_border_color(relay_cards[idx], lv_color_hex(active_border), 0);
    } else {
        lv_label_set_text(val_relays[idx], "OFF");
        lv_obj_set_style_text_color(val_relays[idx], lv_color_hex(is_dark_mode ? 0x64748b : 0x94a3b8), 0);
        lv_obj_set_style_bg_color(relay_cards[idx], lv_color_hex(inactive_bg), 0);
        lv_obj_set_style_border_color(relay_cards[idx], lv_color_hex(inactive_border), 0);
    }
}

static void relay_touch_cb(lv_event_t *e) {
    int idx = (int)(intptr_t)lv_event_get_user_data(e);
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        if (idx == 0 || idx == 3) {
            g_relay_cmd[idx] ^= 1;
        } else if (idx == 1 || idx == 2) {
            g_relay_cmd[idx] = 1;
            pump_until_ms[idx] = to_ms_since_boot(get_absolute_time()) + PUMP_RUN_MS;
        }
        update_relay_ui(idx);
    }
}

static void update_pump_timer(void) {
    uint64_t now = to_ms_since_boot(get_absolute_time());
    for (int idx = 1; idx <= 2; idx++) {
        if (g_relay_cmd[idx] && pump_until_ms[idx] > 0) {
            if (now >= pump_until_ms[idx]) {
                g_relay_cmd[idx] = 0;
                pump_until_ms[idx] = 0;
            }
            update_relay_ui(idx);
        }
    }
}

static void theme_toggle_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        is_dark_mode = !is_dark_mode;
        lv_obj_clean(lv_scr_act());
        modal_bg = NULL; 
        create_dashboard();
        update_labels(&g_sensor);
    }
}

static void close_modal_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        lv_obj_del(modal_bg);
        modal_bg = NULL;
        chart_obj = NULL;
        current_graph_sensor = -1;
    }
}

static void sensor_touch_cb(lv_event_t *e) {
    int sensor_idx = (int)(intptr_t)lv_event_get_user_data(e);
    if (lv_event_get_code(e) == LV_EVENT_CLICKED && modal_bg == NULL) {
        current_graph_sensor = sensor_idx;
        
        modal_bg = lv_obj_create(lv_scr_act());
        lv_obj_set_size(modal_bg, 470, 420);
        lv_obj_center(modal_bg);
        lv_obj_set_style_bg_color(modal_bg, lv_color_hex(is_dark_mode ? 0x1e293b : 0xffffff), 0);
        lv_obj_set_style_border_color(modal_bg, lv_color_hex(0x334155), 0);
        lv_obj_set_style_border_width(modal_bg, 2, 0);
        lv_obj_set_style_shadow_width(modal_bg, 30, 0);
        lv_obj_set_style_radius(modal_bg, 12, 0);
        lv_obj_clear_flag(modal_bg, LV_OBJ_FLAG_SCROLLABLE);

        lv_obj_t *title = lv_label_create(modal_bg);
        lv_label_set_text(title, sensor_names[sensor_idx]);
        lv_obj_set_style_text_font(title, &lv_font_montserrat_16, 0);
        lv_obj_set_style_text_color(title, lv_color_hex(is_dark_mode ? 0xf1f5f9 : 0x1e293b), 0);
        lv_obj_align(title, LV_ALIGN_TOP_LEFT, 15, 10);

        val_modal_curr = lv_label_create(modal_bg);
        lv_obj_align(val_modal_curr, LV_ALIGN_TOP_LEFT, 15, 35);
        lv_obj_set_style_text_font(val_modal_curr, &lv_font_montserrat_16, 0);
        lv_obj_set_style_text_color(val_modal_curr, lv_color_hex(0x38bdf8), 0);

        lv_obj_t *btn_close = lv_btn_create(modal_bg);
        lv_obj_set_size(btn_close, 50, 35);
        lv_obj_align(btn_close, LV_ALIGN_TOP_RIGHT, -5, 5);
        lv_obj_set_style_bg_color(btn_close, lv_color_hex(0xef4444), 0);
        lv_obj_add_event_cb(btn_close, close_modal_cb, LV_EVENT_CLICKED, NULL);
        lv_obj_t *lbl_close = lv_label_create(btn_close);
        lv_label_set_text(lbl_close, LV_SYMBOL_CLOSE);
        lv_obj_center(lbl_close);

        chart_obj = lv_chart_create(modal_bg);
        lv_obj_set_size(chart_obj, 380, 280);
        lv_obj_align(chart_obj, LV_ALIGN_BOTTOM_MID, 25, -45);
        lv_chart_set_type(chart_obj, LV_CHART_TYPE_LINE);
        lv_obj_set_style_bg_color(chart_obj, lv_color_hex(is_dark_mode ? 0x0f172a : 0xf8fafc), 0);
        lv_chart_set_point_count(chart_obj, HISTORY_SIZE);
        lv_chart_set_div_line_count(chart_obj, 5, 5);
        
        // Y축 눈금 및 수치 추가
        lv_chart_set_axis_tick(chart_obj, LV_CHART_AXIS_PRIMARY_Y, 10, 5, 6, 2, true, 40);
        // X축 시간 흐름 표시 (-10m, -5m, Now)
        lv_chart_set_axis_tick(chart_obj, LV_CHART_AXIS_PRIMARY_X, 10, 5, 5, 1, true, 30);
        
        chart_ser = lv_chart_add_series(chart_obj, lv_color_hex(0x38bdf8), LV_CHART_AXIS_PRIMARY_Y);
        
        float min_v = g_history[sensor_idx][0];
        float max_v = g_history[sensor_idx][0];
        for(int i=0; i<HISTORY_SIZE; i++) {
            if(g_history[sensor_idx][i] < min_v) min_v = g_history[sensor_idx][i];
            if(g_history[sensor_idx][i] > max_v) max_v = g_history[sensor_idx][i];
            lv_chart_set_next_value(chart_obj, chart_ser, (lv_coord_t)(g_history[sensor_idx][i] * 10));
        }
        
        if(max_v == min_v) { max_v += 1.0; min_v -= 1.0; }
        lv_chart_set_range(chart_obj, LV_CHART_AXIS_PRIMARY_Y, (lv_coord_t)(min_v * 10 - 10), (lv_coord_t)(max_v * 10 + 10));
        
        char vbuf[32];
        snprintf(vbuf, sizeof(vbuf), "%.1f %s", g_history[sensor_idx][HISTORY_SIZE-1], sensor_units[sensor_idx]);
        lv_label_set_text(val_modal_curr, vbuf);
        
        lv_obj_t *xlabel = lv_label_create(modal_bg);
        lv_label_set_text(xlabel, "-10m             -5m             Now");
        lv_obj_set_style_text_font(xlabel, &lv_font_montserrat_12, 0);
        lv_obj_set_style_text_color(xlabel, lv_color_hex(0x94a3b8), 0);
        lv_obj_align(xlabel, LV_ALIGN_BOTTOM_MID, 25, -20);

        lv_chart_refresh(chart_obj);
    }
}

static lv_obj_t *make_card(lv_obj_t *parent, const char *title, uint32_t accent, int sensor_idx, lv_obj_t **out_val) {
    uint32_t bg_color = is_dark_mode ? 0x1e293b : 0xffffff;
    uint32_t border_color = is_dark_mode ? 0x334155 : 0xe2e8f0;
    uint32_t title_color = is_dark_mode ? 0x94a3b8 : 0x64748b;

    lv_obj_t *card = lv_obj_create(parent);
    lv_obj_set_style_bg_color(card, lv_color_hex(bg_color), 0);
    lv_obj_set_style_border_color(card, lv_color_hex(border_color), 0);
    lv_obj_set_style_border_width(card, 1, 0);
    lv_obj_set_style_radius(card, 8, 0);
    lv_obj_set_style_pad_all(card, 8, 0);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(card, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);

    if (sensor_idx >= 0) {
        lv_obj_add_flag(card, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(card, sensor_touch_cb, LV_EVENT_CLICKED, (void*)(intptr_t)sensor_idx);
    }

    lv_obj_t *lbl = lv_label_create(card);
    lv_label_set_text(lbl, title);
    lv_obj_set_style_text_color(lbl, lv_color_hex(title_color), 0);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_12, 0);

    lv_obj_t *val = lv_label_create(card);
    lv_label_set_text(val, "--");
    lv_obj_set_style_text_color(val, lv_color_hex(accent), 0);
    lv_obj_set_style_text_font(val, &lv_font_montserrat_16, 0);
    lv_obj_set_style_pad_top(val, 2, 0);

    *out_val = val;
    return card;
}

static void create_dashboard(void) {
    lv_obj_t *scr = lv_scr_act();
    uint32_t bg_scr = is_dark_mode ? 0x0f172a : 0xf1f5f9;
    uint32_t bg_hdr = is_dark_mode ? 0x1e293b : 0xffffff;
    uint32_t text_hdr = is_dark_mode ? 0xf1f5f9 : 0x1e293b;

    lv_obj_set_style_bg_color(scr, lv_color_hex(bg_scr), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *hdr = lv_obj_create(scr);
    lv_obj_set_size(hdr, 480, 44);
    lv_obj_set_pos(hdr, 0, 0);
    lv_obj_set_style_bg_color(hdr, lv_color_hex(bg_hdr), 0);
    lv_obj_set_style_border_width(hdr, 0, 0);
    lv_obj_set_style_radius(hdr, 0, 0);
    lv_obj_clear_flag(hdr, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = lv_label_create(hdr);
    lv_label_set_text(title, "Hunet Smart Dashboard");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(title, lv_color_hex(text_hdr), 0);
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 12, 0);

    lv_obj_t *btn_theme = lv_btn_create(hdr);
    lv_obj_set_size(btn_theme, 32, 32);
    lv_obj_align(btn_theme, LV_ALIGN_RIGHT_MID, -8, 0);
    lv_obj_set_style_bg_opa(btn_theme, 0, 0);
    lv_obj_set_style_shadow_width(btn_theme, 0, 0);
    lv_obj_add_event_cb(btn_theme, theme_toggle_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *lbl_theme = lv_label_create(btn_theme);
    lv_label_set_text(lbl_theme, LV_SYMBOL_SETTINGS);
    lv_obj_set_style_text_color(lbl_theme, lv_color_hex(is_dark_mode ? 0x94a3b8 : 0x64748b), 0);
    lv_obj_center(lbl_theme);

    val_sys_info = lv_label_create(hdr);
    lv_label_set_text(val_sys_info, "WAITING...");
    lv_obj_set_style_text_font(val_sys_info, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(val_sys_info, lv_color_hex(0x64748b), 0);
    lv_obj_align(val_sys_info, LV_ALIGN_RIGHT_MID, -40, 0);

    lv_obj_t *grid = lv_obj_create(scr);
    lv_obj_set_size(grid, 480, 356);
    lv_obj_set_pos(grid, 0, 44);
    lv_obj_set_style_bg_color(grid, lv_color_hex(bg_scr), 0);
    lv_obj_set_style_border_width(grid, 0, 0);
    lv_obj_set_style_radius(grid, 0, 0);
    lv_obj_set_style_pad_all(grid, 6, 0);
    lv_obj_set_style_pad_gap(grid, 6, 0);
    lv_obj_set_flex_flow(grid, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(grid, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_clear_flag(grid, LV_OBJ_FLAG_SCROLLABLE);

    int cw = (480 - 6*2 - 6*2) / 3;
    int ch = (356 - 6*2 - 6*3) / 4;

    make_card(grid, "Air Temp",  0xfb923c, 0, &val_air_temp);  lv_obj_set_size(lv_obj_get_child(grid, 0), cw, ch);
    make_card(grid, "Humidity",  0x38bdf8, 1, &val_humidity);  lv_obj_set_size(lv_obj_get_child(grid, 1), cw, ch);
    make_card(grid, "Solar",     0xfacc15, 2, &val_solar);     lv_obj_set_size(lv_obj_get_child(grid, 2), cw, ch);
    make_card(grid, "Moisture",  0x34d399, 3, &val_moisture);  lv_obj_set_size(lv_obj_get_child(grid, 3), cw, ch);
    make_card(grid, "Soil Temp", 0xfbbf24, 4, &val_soil_temp); lv_obj_set_size(lv_obj_get_child(grid, 4), cw, ch);
    make_card(grid, "CO2",       0x6ee7b7, 5, &val_co2);       lv_obj_set_size(lv_obj_get_child(grid, 5), cw, ch);
    make_card(grid, "EC",        0xa78bfa, 6, &val_ec);        lv_obj_set_size(lv_obj_get_child(grid, 6), cw, ch);
    make_card(grid, "pH",        0xf472b6, 7, &val_ph);        lv_obj_set_size(lv_obj_get_child(grid, 7), cw, ch);
    make_card(grid, "Nitrogen(N)", 0x4ade80, 8, &val_n);       lv_obj_set_size(lv_obj_get_child(grid, 8), cw, ch);
    make_card(grid, "Phosph(P)", 0xf87171, 9, &val_p);         lv_obj_set_size(lv_obj_get_child(grid, 9), cw, ch);
    make_card(grid, "Potass(K)", 0x60a5fa, 10, &val_k);        lv_obj_set_size(lv_obj_get_child(grid, 10), cw, ch);
    make_card(grid, "Pico Status", 0x94a3b8, -1, &val_sys_info); lv_obj_set_size(lv_obj_get_child(grid, 11), cw, ch);

    lv_obj_t *footer = lv_obj_create(scr);
    lv_obj_set_size(footer, 480, 80);
    lv_obj_set_pos(footer, 0, 400);
    lv_obj_set_style_bg_color(footer, lv_color_hex(bg_hdr), 0);
    lv_obj_set_style_border_width(footer, 0, 0);
    lv_obj_set_style_radius(footer, 0, 0);
    lv_obj_set_style_pad_all(footer, 8, 0);
    lv_obj_set_style_pad_gap(footer, 8, 0);
    lv_obj_set_flex_flow(footer, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(footer, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_clear_flag(footer, LV_OBJ_FLAG_SCROLLABLE);

    int rw = (480 - 8*2 - 8*3) / 4;
    for (int i = 0; i < 4; i++) {
        relay_cards[i] = lv_obj_create(footer);
        lv_obj_set_size(relay_cards[i], rw, 64);
        lv_obj_set_style_radius(relay_cards[i], 8, 0);
        lv_obj_set_style_border_width(relay_cards[i], 1, 0);
        lv_obj_set_style_pad_all(relay_cards[i], 6, 0);
        lv_obj_clear_flag(relay_cards[i], LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_flex_flow(relay_cards[i], LV_FLEX_FLOW_COLUMN);
        lv_obj_set_flex_align(relay_cards[i], LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

        lbl_relays[i] = lv_label_create(relay_cards[i]);
        const char *rname = "UNUSED";
        if (i == 0) rname = "FAN";
        if (i == 1) rname = "PUMP 1";
        if (i == 2) rname = "PUMP 2";
        if (i == 3) rname = "LED";
        lv_label_set_text(lbl_relays[i], rname);
        lv_obj_set_style_text_font(lbl_relays[i], &lv_font_montserrat_12, 0);
        lv_obj_set_style_text_color(lbl_relays[i], lv_color_hex(is_dark_mode ? 0x94a3b8 : 0x64748b), 0);

        val_relays[i] = lv_label_create(relay_cards[i]);
        lv_obj_set_style_text_font(val_relays[i], &lv_font_montserrat_16, 0);
        
        if (i == 0 || i == 1 || i == 2 || i == 3) {
            lv_obj_add_flag(relay_cards[i], LV_OBJ_FLAG_CLICKABLE);
            lv_obj_add_event_cb(relay_cards[i], relay_touch_cb, LV_EVENT_CLICKED, (void*)(intptr_t)i);
        }
        update_relay_ui(i);
    }
}

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

    lv_label_set_text(val_sys_info, "CONNECTED");
    lv_obj_set_style_text_color(val_sys_info, lv_color_hex(0x10b981), 0);

    float current_vals[] = {d->air_temp, d->humidity, (float)d->solar, d->moisture, d->soil_temp, (float)d->co2, (float)d->ec, d->ph, (float)d->n, (float)d->p, (float)d->k};
    for(int i=0; i<11; i++) {
        for(int j=0; j<HISTORY_SIZE-1; j++) g_history[i][j] = g_history[i][j+1];
        g_history[i][HISTORY_SIZE-1] = current_vals[i];
    }

    if(modal_bg && chart_obj && current_graph_sensor >= 0) {
        lv_chart_set_next_value(chart_obj, chart_ser, (lv_coord_t)(current_vals[current_graph_sensor] * 10));
        char vbuf[32];
        snprintf(vbuf, sizeof(vbuf), "%.1f %s", current_vals[current_graph_sensor], sensor_units[current_graph_sensor]);
        lv_label_set_text(val_modal_curr, vbuf);
        lv_chart_refresh(chart_obj);
    }
}

static void set_cpu_clock(uint32_t mhz) {
    set_sys_clock_khz(mhz * 1000, true);
    clock_configure(clk_peri, 0, CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLKSRC_PLL_SYS, mhz * 1000 * 1000, mhz * 1000 * 1000);
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
    uart_pico_setup();
    bsp_i2c_init();
    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();
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
        update_pump_timer();
        lv_timer_handler();
        sleep_ms(LVGL_TICK_MS);
    }
}
