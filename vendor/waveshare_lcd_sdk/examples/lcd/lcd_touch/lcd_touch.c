#include <stdio.h>
#include "pico/stdlib.h"
#include "bsp_i2c.h"
#include "bsp_gt911.h"
// #include "bsp_st7701_rgb.h"
// #include "bsp_lcd_brightness.h"

#include "hardware/clocks.h"
#include "bsp_st7701.h"
#include "pio_rgb.h"

#define LCD_WIDTH 480
#define LCD_HEIGHT 480
uint16_t color_arr[6] = {0xf800, 0x07e0, 0x001f, 0xf80f, 0xf01f, 0xffff};

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

int main()
{
    stdio_init_all();
    set_cpu_clock(240);
    bsp_i2c_init();

    bsp_display_interface_t *display_if;
    pio_rgb_info_t rgb_info;
    rgb_info.width = LCD_WIDTH;
    rgb_info.height = LCD_HEIGHT;
    rgb_info.transfer_size = LCD_WIDTH * 80;
    rgb_info.pclk_freq = BSP_LCD_PCLK_FREQ;
    rgb_info.mode.double_buffer = false;
    rgb_info.mode.enabled_transfer = false;
    rgb_info.mode.enabled_psram = false;
    rgb_info.framebuffer1 = malloc(LCD_WIDTH * LCD_HEIGHT * sizeof(uint16_t));
    rgb_info.dma_flush_done_cb = NULL;

    bsp_display_info_t display_info;
    display_info.width = LCD_WIDTH;
    display_info.height = LCD_HEIGHT;
    display_info.brightness = 100;
    display_info.dma_flush_done_cb = NULL;
    display_info.user_data = &rgb_info;
    bsp_display_new_st7701(&display_if, &display_info);
    display_if->init();

    bsp_touch_interface_t *touch_if;
    bsp_touch_info_t touch_info;
    touch_info.width = LCD_WIDTH;
    touch_info.height = LCD_HEIGHT;
    touch_info.rotation = 0;
    bsp_touch_new_gt911(&touch_if, &touch_info);
    touch_if->init();
    bsp_touch_data_t touch_data;

    uint16_t *buffer = rgb_info.framebuffer1;
    uint16_t pixel_size = 4;
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
                if (touch_data.coords[i].x > LCD_WIDTH - pixel_size - 1)
                    touch_data.coords[i].x = LCD_WIDTH - pixel_size - 1;
                if (touch_data.coords[i].y > LCD_HEIGHT - pixel_size - 1)
                    touch_data.coords[i].y = LCD_HEIGHT - pixel_size - 1;

                for (int w = 0; w < pixel_size; w++)
                {
                    for (int h = 0; h < pixel_size; h++)
                    {
                        buffer[LCD_WIDTH * (touch_data.coords[i].y + h) + touch_data.coords[i].x + w] = color_arr[i];
                    }
                }
            }
            printf("\n");
        }
        sleep_ms(10);
    }
}
