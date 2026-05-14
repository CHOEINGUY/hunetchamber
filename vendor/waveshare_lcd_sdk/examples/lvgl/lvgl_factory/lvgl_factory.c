#include <stdio.h>
#include "pico/stdlib.h"

#include "bsp_i2c.h"
#include "../lv_port/lv_port_disp.h"
#include "../lv_port/lv_port_indev.h"
#include "demos/lv_demos.h"
#include "lvgl.h"

#include "lvgl_ui.h"
#include "hardware/pll.h"
#include "hardware/clocks.h"
#include "hardware/structs/pll.h"
#include "hardware/structs/clocks.h"
#include "bsp_qmi8658.h"
#include "bsp_pcf85063.h"
#include "bsp_battery.h"
#include "bsp_buzzer.h"
#include "hardware/adc.h"

#include "pio_rgb.h"
#include "bsp_gt911.h"

#include <stdio.h>

#include "hardware/gpio.h"
#include "hardware/sync.h"
#include "hardware/structs/ioqspi.h"
#include "hardware/structs/sio.h"

#define LVGL_TICK_PERIOD_MS 5

uint16_t color_arr[6] = {0xf800, 0x07e0, 0x001f, 0xf80f, 0xf01f, 0xffff};
bool __no_inline_not_in_flash_func(get_bootsel_button)() {
    const uint CS_PIN_INDEX = 1;

    // Must disable interrupts, as interrupt handlers may be in flash, and we
    // are about to temporarily disable flash access!
    uint32_t flags = save_and_disable_interrupts();

    // Set chip select to Hi-Z
    hw_write_masked(&ioqspi_hw->io[CS_PIN_INDEX].ctrl,
                    GPIO_OVERRIDE_LOW << IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_LSB,
                    IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_BITS);

    // Note we can't call into any sleep functions in flash right now
    for (volatile int i = 0; i < 1000; ++i);

    // The HI GPIO registers in SIO can observe and control the 6 QSPI pins.
    // Note the button pulls the pin *low* when pressed.
    #define CS_BIT SIO_GPIO_HI_IN_QSPI_CSN_BITS

    bool button_state = !(sio_hw->gpio_hi_in & CS_BIT);

    // Need to restore the state of chip select, else we are going to have a
    // bad time when we return to code in flash!
    hw_write_masked(&ioqspi_hw->io[CS_PIN_INDEX].ctrl,
                    GPIO_OVERRIDE_NORMAL << IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_LSB,
                    IO_QSPI_GPIO_QSPI_SS_CTRL_OEOVER_BITS);

    restore_interrupts(flags);

    return button_state;
}

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

int boot = 0;
static bool repeating_boot_scan_cb(struct repeating_timer *t)
{
    if (get_bootsel_button())
    {
        boot = 1;
    }
    return true;
}

int main()
{
    struct tm now_tm;
    static struct repeating_timer lvgl_timer;
    static struct repeating_timer boot_timer;

    stdio_init_all();
    sleep_ms(100);
    set_cpu_clock(260);
    
    bsp_i2c_init();
    bsp_battery_init();
    adc_set_temp_sensor_enabled(true);
    bsp_qmi8658_init();
    bsp_pcf85063_init();
    bsp_buzzer_init();
    bsp_pcf85063_get_time(&now_tm);

    if (now_tm.tm_year < 125 || now_tm.tm_year > 130)
    {
        now_tm.tm_year = 2025 - 1900; // The year starts from 1900
        now_tm.tm_mon = 1 - 1;        // Months start from 0 (November = 10)
        now_tm.tm_mday = 1;           // Day of the month
        now_tm.tm_hour = 12;          // Hour
        now_tm.tm_min = 0;            // Minute
        now_tm.tm_sec = 0;            // Second
        now_tm.tm_isdst = -1;         // Automatically detect daylight saving time
        bsp_pcf85063_set_time(&now_tm);
    }

    lv_init();
    lv_port_disp_init();
    lv_port_indev_init();

    lv_obj_t *lable = NULL;
    lable = lv_label_create(lv_scr_act());
    lv_label_set_text(lable, "Touch testing mode Exit with BOOT button");
    lv_obj_align(lable, LV_ALIGN_CENTER, 0, 0);
    lv_timer_handler();

    bsp_touch_data_t touch_data;
    uint16_t *buffer = pio_rgb_get_free_framebuffer();
    bsp_touch_interface_t *touch_if = bsp_gt911_get_touch_interface();
    uint16_t pixel_size = 4;
    add_repeating_timer_ms(100, repeating_boot_scan_cb, NULL, &boot_timer);    

    while (1)
    {
        touch_if->read();
        if (touch_if->get_data(&touch_data))
        {
            if (touch_data.points > 1)
                pixel_size = 20;
            else 
                pixel_size = 4;
            
            for (size_t i = 0; i < touch_data.points; i++)
            {
                printf("x[%d]: %d, y[%d]: %d  ", i, touch_data.coords[i].x, i, touch_data.coords[i].y);
                if (touch_data.coords[i].x > 479 - pixel_size)
                    touch_data.coords[i].x = 479 - pixel_size;
                if (touch_data.coords[i].y > 479 - pixel_size)
                    touch_data.coords[i].y = 479 - pixel_size;

                for (int w = 0; w < pixel_size; w++)
                {
                    for (int h = 0; h < pixel_size; h++)
                    {
                        buffer[480 * (touch_data.coords[i].y + h) + touch_data.coords[i].x + w] = color_arr[i];
                    }
                }
            }
            printf("\n");
        }
        if (boot == 1)
        {
            cancel_repeating_timer(&boot_timer);
            break;
        }
        sleep_ms(10);
    }
    lv_obj_del(lable);

    add_repeating_timer_ms(LVGL_TICK_PERIOD_MS, repeating_lvgl_timer_cb, NULL, &lvgl_timer);
    // lv_demo_benchmark();
    // lv_demo_music();
    // lv_demo_widgets();
    lvgl_ui_init();

    while (true)
    {
        lv_timer_handler();
        sleep_ms(LVGL_TICK_PERIOD_MS);
    }
}
