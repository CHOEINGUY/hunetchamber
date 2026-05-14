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

#define LVGL_TICK_PERIOD_MS 10
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

int main()
{
    static struct repeating_timer lvgl_timer;
    stdio_init_all();
    sleep_ms(100);
    set_cpu_clock(260);
    bsp_i2c_init();
    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();
    add_repeating_timer_ms(LVGL_TICK_PERIOD_MS, repeating_lvgl_timer_cb, NULL, &lvgl_timer);

    // lv_demo_benchmark();
    lv_demo_music();
    // lv_demo_widgets();
    while (true)
    {
        lv_timer_handler();
        sleep_ms(LVGL_TICK_PERIOD_MS);
    }
}
