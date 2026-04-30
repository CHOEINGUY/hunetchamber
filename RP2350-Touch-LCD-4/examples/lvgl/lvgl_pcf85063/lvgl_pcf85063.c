#include <stdio.h>
#include "pico/stdlib.h"

#include "bsp_i2c.h"
#include "../lv_port/lv_port_disp.h"
#include "../lv_port/lv_port_indev.h"
#include "demos/lv_demos.h"

#include "hardware/pll.h"
#include "hardware/clocks.h"
#include "hardware/structs/pll.h"
#include "hardware/structs/clocks.h"

#include "bsp_qmi8658.h"
#include "bsp_pcf85063.h"

#define LVGL_TICK_PERIOD_MS 10

lv_obj_t *label_time;
lv_obj_t *label_date;

lv_timer_t *pcf85063_timer = NULL;


lv_timer_t *qmi8658_timer = NULL;

void set_cpu_clock(uint32_t freq_Mhz)
{
    set_sys_clock_khz(freq_Mhz * 1000, true);
    clock_configure(
        clk_peri,
        0,
        CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLKSRC_PLL_SYS,
        freq_Mhz * 1000 * 1000,
        freq_Mhz * 1000 * 1000);
}

static bool repeating_lvgl_timer_cb(struct repeating_timer *t)
{
    lv_tick_inc(LVGL_TICK_PERIOD_MS);
    return true;
}

static void pcf85063_callback(lv_timer_t *timer)
{
    struct tm now_tm;
    bsp_pcf85063_get_time(&now_tm);
    lv_label_set_text_fmt(label_time, "%02d:%02d:%02d", now_tm.tm_hour, now_tm.tm_min, now_tm.tm_sec);
    lv_label_set_text_fmt(label_date, "%04d-%02d-%02d", now_tm.tm_year + 1900, now_tm.tm_mon + 1, now_tm.tm_mday);
}

void lvgl_pcf85063_ui_init(void)
{
    lv_obj_t *list = lv_list_create(lv_scr_act());
    lv_obj_set_size(list, lv_pct(70), lv_pct(70));
    lv_obj_align(list, LV_ALIGN_CENTER, 0, 0);

    lv_obj_t *list_item = lv_list_add_btn(list, NULL, "time");
    label_time = lv_label_create(list_item);
    lv_label_set_text(label_time, "12:00:00");

    list_item = lv_list_add_btn(list, NULL, "date");
    label_date = lv_label_create(list_item);
    lv_label_set_text(label_date, "2024-12-01");

    pcf85063_timer = lv_timer_create(pcf85063_callback, 1000, NULL);
}

int main()
{
    struct tm now_tm;
    static struct repeating_timer lvgl_timer;
    stdio_init_all();
    sleep_ms(100);
    set_cpu_clock(240);
    bsp_i2c_init();
    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();
    add_repeating_timer_ms(LVGL_TICK_PERIOD_MS, repeating_lvgl_timer_cb, NULL, &lvgl_timer);

    bsp_pcf85063_init();

    lvgl_pcf85063_ui_init();

    bsp_pcf85063_get_time(&now_tm);

    if (now_tm.tm_year < 124 || now_tm.tm_year > 130)
    {
        now_tm.tm_year = 2025 - 1900; // The year starts from 1900
        now_tm.tm_mon = 1 - 1;       // Months start from 0 (November = 10)
        now_tm.tm_mday = 1;           // Day of the month
        now_tm.tm_hour = 12;          // Hour
        now_tm.tm_min = 0;            // Minute
        now_tm.tm_sec = 0;            // Second
        now_tm.tm_isdst = -1;         // Automatically detect daylight saving time
        bsp_pcf85063_set_time(&now_tm);
    }

    // lv_demo_benchmark();
    // lv_demo_music();
    // lv_demo_widgets();
    while (true)
    {
        lv_timer_handler();
        sleep_ms(LVGL_TICK_PERIOD_MS);
    }
}
