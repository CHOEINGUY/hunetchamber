#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "bsp_st7701.h"
#include "pio_rgb.h"
#include "bsp_sd_card.h"

#define LCD_WIDTH 480
#define LCD_HEIGHT 240

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

extern uint16_t test_count;

int main()
{
    stdio_init_all();
    sleep_ms(100);
    set_cpu_clock(240);

    bsp_display_interface_t *display_if;
    pio_rgb_info_t rgb_info;
    rgb_info.width = LCD_WIDTH;
    rgb_info.height = LCD_HEIGHT;
    rgb_info.transfer_size = LCD_WIDTH * 120;
    rgb_info.pclk_freq = BSP_LCD_PCLK_FREQ;
    rgb_info.mode.double_buffer = false;
    rgb_info.mode.enabled_transfer = true;
    rgb_info.mode.enabled_psram = false;
    rgb_info.framebuffer1 = malloc(LCD_WIDTH * LCD_HEIGHT * sizeof(uint16_t));
    // rgb_info.framebuffer2 = rp_mem_malloc(LCD_WIDTH * LCD_HEIGHT * sizeof(uint16_t));
    // rgb_info.transfer_buffer1 = malloc(rgb_info.transfer_size * sizeof(uint16_t));
    // rgb_info.transfer_buffer2 = malloc(rgb_info.transfer_size * sizeof(uint16_t));
    rgb_info.dma_flush_done_cb = NULL;

    bsp_display_info_t display_info;
    display_info.width = LCD_WIDTH;
    display_info.height = LCD_HEIGHT;
    display_info.brightness = 100;
    display_info.dma_flush_done_cb = NULL;
    display_info.user_data = &rgb_info;
    bsp_display_new_st7701(&display_if, &display_info);
    display_if->init();

    uint16_t *buffer = rgb_info.framebuffer1;
    while (true)
    {
        for (size_t i = 0; i < display_info.width * display_info.height; i++)
        {
            buffer[i] = 0xf800;
        }
        sleep_ms(2000);

        for (size_t i = 0; i < display_info.width * display_info.height; i++)
        {
            buffer[i] = 0x07e0;
        }
        display_if->flush_dma(NULL, NULL);
        sleep_ms(2000);

        for (size_t i = 0; i < display_info.width * display_info.height; i++)
        {
            buffer[i] = 0x001f;
        }
        sleep_ms(2000);
    }
}
