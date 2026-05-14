#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/uart.h"
#include "bsp_i2c.h"
#include "../lvgl/lv_port/lv_port_disp.h"
#include "../lvgl/lv_port/lv_port_indev.h"

#define PICO_UART       uart1
#define PICO_UART_TX    8
#define PICO_UART_RX    9
#define PICO_UART_BAUD  115200

#define LVGL_TICK_MS    10
#define RX_BUF_SIZE     256
#define COMMAND_GAP_MS  80

typedef struct {
    bool has_status;
    bool fridge_on;
    bool armed;
    bool auto_mode;
    int fan_percent;
    int led_percent;
    float target_c;
    float band_c;
    float sensor_c;
    float humidity;
    int wait_s;
    int on_wait_s;
    int state_elapsed_s;
    int sensor_age_s;
    char reason[40];
    uint64_t last_status_ms;
} FridgeState;

static FridgeState g_state = {
    .target_c = 15.0f,
    .band_c = 0.5f,
    .sensor_c = -1000.0f,
    .humidity = -1.0f,
    .reason = "boot",
};

static char rx_buf[RX_BUF_SIZE];
static int rx_len = 0;

static bool pending_target = false;
static bool pending_auto = false;
static bool pending_arm = false;
static bool pending_fan = false;
static bool pending_led = false;
static float pending_target_c = 15.0f;
static bool pending_auto_mode = false;
static bool pending_armed = false;
static int pending_fan_percent = 0;
static int pending_led_percent = 0;
static uint64_t last_command_ms = 0;

static lv_obj_t *lbl_link;
static lv_obj_t *lbl_temp;
static lv_obj_t *lbl_target;
static lv_obj_t *lbl_humidity;
static lv_obj_t *lbl_fridge;
static lv_obj_t *lbl_auto;
static lv_obj_t *lbl_arm;
static lv_obj_t *lbl_wait;
static lv_obj_t *lbl_elapsed;
static lv_obj_t *lbl_reason;
static lv_obj_t *btn_auto;
static lv_obj_t *btn_arm;
static lv_obj_t *btn_fan_down;
static lv_obj_t *btn_fan_up;
static lv_obj_t *btn_led_down;
static lv_obj_t *btn_led_up;
static lv_obj_t *lbl_btn_auto;
static lv_obj_t *lbl_btn_arm;
static lv_obj_t *lbl_btn_fan_down;
static lv_obj_t *lbl_btn_fan_up;
static lv_obj_t *lbl_btn_led_down;
static lv_obj_t *lbl_btn_led_up;

static void update_labels(void);

static void set_label_text_if_changed(lv_obj_t *label, const char *text) {
    const char *old = lv_label_get_text(label);
    if (!old || strcmp(old, text) != 0) {
        lv_label_set_text(label, text);
    }
}

static void set_link_status(const char *text, uint32_t color) {
    set_label_text_if_changed(lbl_link, text);
    lv_obj_set_style_text_color(lbl_link, lv_color_hex(color), 0);
}

static void set_cpu_clock(uint32_t mhz) {
    set_sys_clock_khz(mhz * 1000, true);
    clock_configure(clk_peri, 0,
        CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLKSRC_PLL_SYS,
        mhz * 1000 * 1000,
        mhz * 1000 * 1000);
}

static bool lvgl_tick_cb(struct repeating_timer *t) {
    (void)t;
    lv_tick_inc(LVGL_TICK_MS);
    return true;
}

static void uart_link_setup(void) {
    uart_init(PICO_UART, PICO_UART_BAUD);
    gpio_set_function(PICO_UART_TX, GPIO_FUNC_UART);
    gpio_set_function(PICO_UART_RX, GPIO_FUNC_UART);
}

static void uart_send_line(const char *cmd) {
    uart_write_blocking(PICO_UART, (const uint8_t *)cmd, strlen(cmd));
    uart_write_blocking(PICO_UART, (const uint8_t *)"\n", 1);
}

static void mark_command_pending(void) {
    set_link_status("SENT", 0xfacc15);
}

static bool parse_bool_value(const char *v) {
    return strcmp(v, "1") == 0 || strcmp(v, "on") == 0 || strcmp(v, "ON") == 0;
}

static bool parse_float_value(const char *v, float *out) {
    if (strcmp(v, "na") == 0 || strcmp(v, "nan") == 0) return false;
    char *end = NULL;
    float f = strtof(v, &end);
    if (end == v) return false;
    *out = f;
    return true;
}

static int clamp_int(int value, int low, int high) {
    if (value < low) return low;
    if (value > high) return high;
    return value;
}

static float clamp_float(float value, float low, float high) {
    if (value < low) return low;
    if (value > high) return high;
    return value;
}

static float quantize_target(float value) {
    float clamped = clamp_float(value, 0.0f, 25.0f);
    int half_steps = (int)(clamped * 2.0f + 0.5f);
    return half_steps / 2.0f;
}

static void format_duration(int seconds, char *out, size_t out_size) {
    int s = seconds < 0 ? 0 : seconds;
    int h = s / 3600;
    int m = (s % 3600) / 60;
    int sec = s % 60;
    if (h > 0) {
        snprintf(out, out_size, "%dh %dm", h, m);
    } else if (m > 0) {
        snprintf(out, out_size, "%dm %ds", m, sec);
    } else {
        snprintf(out, out_size, "%ds", sec);
    }
}

static int seconds_since_last_status(void) {
    if (!g_state.last_status_ms) return 0;
    uint64_t now = to_ms_since_boot(get_absolute_time());
    return (int)((now - g_state.last_status_ms) / 1000);
}

static void queue_target(float value) {
    g_state.target_c = quantize_target(value);
    pending_target_c = g_state.target_c;
    pending_target = true;
    mark_command_pending();
    update_labels();
}

static void queue_auto(bool enabled) {
    g_state.auto_mode = enabled;
    if (enabled) {
        g_state.armed = true;
        pending_armed = true;
        pending_arm = true;
    }
    pending_auto_mode = enabled;
    pending_auto = true;
    mark_command_pending();
    update_labels();
}

static void queue_arm(bool enabled) {
    g_state.armed = enabled;
    if (!enabled) {
        g_state.auto_mode = false;
        pending_auto_mode = false;
        pending_auto = true;
    }
    pending_armed = enabled;
    pending_arm = true;
    mark_command_pending();
    update_labels();
}

static void queue_fan(int percent) {
    g_state.fan_percent = clamp_int(percent, 0, 100);
    pending_fan_percent = g_state.fan_percent;
    pending_fan = true;
    mark_command_pending();
    update_labels();
}

static void queue_led(int percent) {
    g_state.led_percent = clamp_int(percent, 0, 100);
    pending_led_percent = g_state.led_percent;
    pending_led = true;
    mark_command_pending();
    update_labels();
}

static void service_command_queue(uint64_t now) {
    if (now - last_command_ms < COMMAND_GAP_MS) return;

    char cmd[32];
    if (pending_target) {
        snprintf(cmd, sizeof(cmd), "target %.1f", pending_target_c);
        pending_target = false;
    } else if (pending_auto) {
        snprintf(cmd, sizeof(cmd), "auto %d", pending_auto_mode ? 1 : 0);
        pending_auto = false;
    } else if (pending_arm) {
        snprintf(cmd, sizeof(cmd), "%s", pending_armed ? "arm" : "disarm");
        pending_arm = false;
    } else if (pending_fan) {
        snprintf(cmd, sizeof(cmd), "fan %d", pending_fan_percent);
        pending_fan = false;
    } else if (pending_led) {
        snprintf(cmd, sizeof(cmd), "led %d", pending_led_percent);
        pending_led = false;
    } else {
        return;
    }

    uart_send_line(cmd);
    last_command_ms = now;
}

static void parse_status_line(char *line) {
    if (strncmp(line, "STATUS ", 7) != 0) return;

    char *save = NULL;
    char *tok = strtok_r(line + 7, " \r\n", &save);
    while (tok) {
        char *eq = strchr(tok, '=');
        if (eq) {
            *eq = '\0';
            const char *key = tok;
            const char *val = eq + 1;
            float f = 0.0f;

            if (strcmp(key, "on") == 0) g_state.fridge_on = parse_bool_value(val);
            else if (strcmp(key, "armed") == 0 && !pending_arm) g_state.armed = parse_bool_value(val);
            else if (strcmp(key, "auto") == 0 && !pending_auto) g_state.auto_mode = parse_bool_value(val);
            else if (strcmp(key, "fan") == 0 && !pending_fan) g_state.fan_percent = clamp_int(atoi(val), 0, 100);
            else if (strcmp(key, "led") == 0 && !pending_led) g_state.led_percent = clamp_int(atoi(val), 0, 100);
            else if (strcmp(key, "target_c") == 0 && !pending_target && parse_float_value(val, &f)) g_state.target_c = quantize_target(f);
            else if (strcmp(key, "band_c") == 0 && parse_float_value(val, &f)) g_state.band_c = f;
            else if (strcmp(key, "temp_c") == 0 && parse_float_value(val, &f) && f > -40.0f && f < 80.0f) g_state.sensor_c = f;
            else if (strcmp(key, "humidity") == 0 && parse_float_value(val, &f) && f >= 0.0f && f <= 100.0f) g_state.humidity = f;
            else if (strcmp(key, "wait_on_s") == 0) g_state.wait_s = atoi(val);
            else if (strcmp(key, "wait_off_s") == 0) g_state.on_wait_s = atoi(val);
            else if (strcmp(key, "state_elapsed_s") == 0) g_state.state_elapsed_s = atoi(val);
            else if (strcmp(key, "sensor_age_s") == 0) g_state.sensor_age_s = atoi(val);
            else if (strcmp(key, "reason") == 0) {
                snprintf(g_state.reason, sizeof(g_state.reason), "%s", val);
            }
        }
        tok = strtok_r(NULL, " \r\n", &save);
    }

    g_state.has_status = true;
    g_state.last_status_ms = to_ms_since_boot(get_absolute_time());
    update_labels();
}

static void poll_uart(void) {
    while (uart_is_readable(PICO_UART)) {
        char c = uart_getc(PICO_UART);
        if (c == '\r') continue;
        if (rx_len < RX_BUF_SIZE - 1) {
            rx_buf[rx_len++] = c;
            if (c == '\n') {
                rx_buf[rx_len] = '\0';
                parse_status_line(rx_buf);
                rx_len = 0;
            }
        } else {
            rx_len = 0;
        }
    }
}

static lv_obj_t *make_panel(lv_obj_t *parent, int x, int y, int w, int h, const char *title, lv_obj_t **value) {
    lv_obj_t *panel = lv_obj_create(parent);
    lv_obj_set_size(panel, w, h);
    lv_obj_set_pos(panel, x, y);
    lv_obj_set_style_bg_color(panel, lv_color_hex(0x111827), 0);
    lv_obj_set_style_border_color(panel, lv_color_hex(0x263244), 0);
    lv_obj_set_style_border_width(panel, 1, 0);
    lv_obj_set_style_radius(panel, 8, 0);
    lv_obj_set_style_pad_all(panel, 8, 0);
    lv_obj_clear_flag(panel, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(panel);
    lv_label_set_text(t, title);
    lv_obj_set_style_text_font(t, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(t, lv_color_hex(0x94a3b8), 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 0, 0);

    *value = lv_label_create(panel);
    lv_label_set_text(*value, "--");
    lv_obj_set_style_text_font(*value, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(*value, lv_color_hex(0xe5e7eb), 0);
    lv_obj_align(*value, LV_ALIGN_BOTTOM_LEFT, 0, 0);
    return panel;
}

static lv_obj_t *make_button(lv_obj_t *parent, int x, int y, int w, int h, const char *text, lv_event_cb_t cb, lv_obj_t **label_out) {
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_set_size(btn, w, h);
    lv_obj_set_pos(btn, x, y);
    lv_obj_set_style_radius(btn, 8, 0);
    lv_obj_set_style_bg_color(btn, lv_color_hex(0x1f2937), 0);
    lv_obj_set_style_shadow_width(btn, 0, 0);
    lv_obj_add_event_cb(btn, cb, LV_EVENT_CLICKED, NULL);

    lv_obj_t *label = lv_label_create(btn);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_font(label, &lv_font_montserrat_14, 0);
    lv_obj_center(label);
    if (label_out) *label_out = label;
    return btn;
}

static void target_down_cb(lv_event_t *e) {
    (void)e;
    queue_target(g_state.target_c - 0.5f);
}

static void target_up_cb(lv_event_t *e) {
    (void)e;
    queue_target(g_state.target_c + 0.5f);
}

static void auto_cb(lv_event_t *e) {
    (void)e;
    queue_auto(!g_state.auto_mode);
}

static void arm_cb(lv_event_t *e) {
    (void)e;
    queue_arm(!g_state.armed);
}

static void fan_down_cb(lv_event_t *e) {
    (void)e;
    queue_fan(0);
}

static void fan_up_cb(lv_event_t *e) {
    (void)e;
    queue_fan(100);
}

static void led_down_cb(lv_event_t *e) {
    (void)e;
    queue_led(g_state.led_percent - 10);
}

static void led_up_cb(lv_event_t *e) {
    (void)e;
    queue_led(g_state.led_percent + 10);
}

static void style_toggle_button(lv_obj_t *btn, lv_obj_t *label, bool active, const char *on_text, const char *off_text) {
    set_label_text_if_changed(label, active ? on_text : off_text);
    lv_obj_set_style_bg_color(btn, lv_color_hex(active ? 0x0f766e : 0x1f2937), 0);
}

static void style_button(lv_obj_t *btn, lv_obj_t *label, const char *text, bool active) {
    set_label_text_if_changed(label, text);
    lv_obj_set_style_bg_color(btn, lv_color_hex(active ? 0x0f766e : 0x1f2937), 0);
}

static void update_labels(void) {
    char buf[64];
    char dur[24];
    int status_elapsed_s = seconds_since_last_status();
    int wait_on_s = g_state.wait_s - status_elapsed_s;
    int wait_off_s = g_state.on_wait_s - status_elapsed_s;
    int state_elapsed_s = g_state.state_elapsed_s + status_elapsed_s;
    if (wait_on_s < 0) wait_on_s = 0;
    if (wait_off_s < 0) wait_off_s = 0;

    if (g_state.sensor_c > -100.0f) snprintf(buf, sizeof(buf), "%.1f C", g_state.sensor_c);
    else snprintf(buf, sizeof(buf), "-- C");
    set_label_text_if_changed(lbl_temp, buf);
    lv_obj_set_style_text_color(lbl_temp, lv_color_hex(0x38bdf8), 0);

    snprintf(buf, sizeof(buf), "%.1f C  +/- %.1f", g_state.target_c, g_state.band_c);
    set_label_text_if_changed(lbl_target, buf);

    if (g_state.humidity >= 0.0f) snprintf(buf, sizeof(buf), "%.1f %%", g_state.humidity);
    else snprintf(buf, sizeof(buf), "-- %%");
    set_label_text_if_changed(lbl_humidity, buf);

    set_label_text_if_changed(lbl_fridge, g_state.fridge_on ? "ON" : "OFF");
    lv_obj_set_style_text_color(lbl_fridge, lv_color_hex(g_state.fridge_on ? 0x22c55e : 0x94a3b8), 0);

    set_label_text_if_changed(lbl_auto, g_state.auto_mode ? "AUTO" : "MANUAL");
    lv_obj_set_style_text_color(lbl_auto, lv_color_hex(g_state.auto_mode ? 0x22c55e : 0xfacc15), 0);

    set_label_text_if_changed(lbl_arm, g_state.armed ? "ARMED" : "SAFE");
    lv_obj_set_style_text_color(lbl_arm, lv_color_hex(g_state.armed ? 0x22c55e : 0x94a3b8), 0);

    if (wait_on_s > 0) {
        format_duration(wait_on_s, dur, sizeof(dur));
        snprintf(buf, sizeof(buf), "%s left", dur);
    } else {
        snprintf(buf, sizeof(buf), "Ready");
    }
    set_label_text_if_changed(lbl_wait, buf);

    if (wait_off_s > 0) {
        format_duration(wait_off_s, dur, sizeof(dur));
        snprintf(buf, sizeof(buf), "%s left", dur);
    } else {
        snprintf(buf, sizeof(buf), "Ready");
    }
    set_label_text_if_changed(lbl_elapsed, buf);

    format_duration(state_elapsed_s, dur, sizeof(dur));
    snprintf(buf, sizeof(buf), "%s for %s", g_state.fridge_on ? "ON" : "OFF", dur);
    set_label_text_if_changed(lbl_reason, buf);

    style_toggle_button(btn_auto, lbl_btn_auto, g_state.auto_mode, "AUTO ON", "AUTO OFF");
    style_toggle_button(btn_arm, lbl_btn_arm, g_state.armed, "ARMED", "ARM");
    style_button(btn_fan_down, lbl_btn_fan_down, "FAN OFF", false);
    style_button(btn_fan_up, lbl_btn_fan_up, "FAN ON", g_state.fan_percent > 0);
    snprintf(buf, sizeof(buf), "LED -  %d%%", g_state.led_percent);
    style_button(btn_led_down, lbl_btn_led_down, buf, g_state.led_percent > 0);
    snprintf(buf, sizeof(buf), "LED +  %d%%", g_state.led_percent);
    style_button(btn_led_up, lbl_btn_led_up, buf, g_state.led_percent > 0);

    snprintf(buf, sizeof(buf), status_elapsed_s < 5 ? "LIVE" : "WAIT");
    set_link_status(buf, status_elapsed_s < 5 ? 0x22c55e : 0x64748b);
}

static void create_dashboard(void) {
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0x0b1120), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = lv_label_create(scr);
    lv_label_set_text(title, "Fridge Controller");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_20, 0);
    lv_obj_set_style_text_color(title, lv_color_hex(0xf8fafc), 0);
    lv_obj_set_pos(title, 14, 12);

    lbl_link = lv_label_create(scr);
    lv_label_set_text(lbl_link, "WAIT");
    lv_obj_set_style_text_font(lbl_link, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(lbl_link, lv_color_hex(0x64748b), 0);
    lv_obj_align(lbl_link, LV_ALIGN_TOP_RIGHT, -16, 15);

    make_panel(scr, 12, 48, 220, 86, "CURRENT TEMP", &lbl_temp);
    lv_obj_set_style_text_font(lbl_temp, &lv_font_montserrat_20, 0);
    make_panel(scr, 248, 48, 220, 86, "TARGET", &lbl_target);
    make_panel(scr, 12, 144, 104, 64, "HUMIDITY", &lbl_humidity);
    make_panel(scr, 128, 144, 104, 64, "FRIDGE", &lbl_fridge);
    make_panel(scr, 244, 144, 104, 64, "MODE", &lbl_auto);
    make_panel(scr, 360, 144, 108, 64, "ARM", &lbl_arm);
    make_panel(scr, 12, 218, 220, 64, "TURN ON", &lbl_wait);
    make_panel(scr, 248, 218, 220, 64, "TURN OFF", &lbl_elapsed);
    make_panel(scr, 12, 292, 456, 48, "CURRENT STATE", &lbl_reason);

    make_button(scr, 12, 352, 104, 48, "-0.5C", target_down_cb, NULL);
    make_button(scr, 128, 352, 104, 48, "+0.5C", target_up_cb, NULL);
    btn_auto = make_button(scr, 244, 352, 104, 48, "AUTO OFF", auto_cb, &lbl_btn_auto);
    btn_arm = make_button(scr, 360, 352, 108, 48, "ARM", arm_cb, &lbl_btn_arm);

    btn_fan_down = make_button(scr, 12, 412, 104, 48, "FAN OFF", fan_down_cb, &lbl_btn_fan_down);
    btn_fan_up = make_button(scr, 128, 412, 104, 48, "FAN ON", fan_up_cb, &lbl_btn_fan_up);
    btn_led_down = make_button(scr, 244, 412, 104, 48, "LED -", led_down_cb, &lbl_btn_led_down);
    btn_led_up = make_button(scr, 360, 412, 108, 48, "LED +", led_up_cb, &lbl_btn_led_up);

    update_labels();
}

int main(void) {
    static struct repeating_timer lvgl_timer;

    stdio_init_all();
    sleep_ms(100);
    set_cpu_clock(260);
    uart_link_setup();
    bsp_i2c_init();

    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();
    add_repeating_timer_ms(LVGL_TICK_MS, lvgl_tick_cb, NULL, &lvgl_timer);
    create_dashboard();

    uint64_t last_status_request_ms = 0;
    uint64_t last_ui_refresh_ms = 0;
    bool last_status_stale = true;
    while (true) {
        poll_uart();

        uint64_t now = to_ms_since_boot(get_absolute_time());
        service_command_queue(now);

        bool status_stale = !g_state.last_status_ms || (now - g_state.last_status_ms > 5000);
        if (status_stale && now - last_status_request_ms > 3000) {
            uart_send_line("status");
            last_status_request_ms = now;
        }

        if (status_stale != last_status_stale) {
            set_link_status(status_stale ? "WAIT" : "LIVE", status_stale ? 0x64748b : 0x22c55e);
            last_status_stale = status_stale;
        }

        if (now - last_ui_refresh_ms >= 500) {
            update_labels();
            last_ui_refresh_ms = now;
        }

        lv_timer_handler();
        sleep_ms(LVGL_TICK_MS);
    }
}
