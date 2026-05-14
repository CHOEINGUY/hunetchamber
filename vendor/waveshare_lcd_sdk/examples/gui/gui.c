#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "bsp_st7701.h"
#include "pio_rgb.h"
#include "GUI_Paint.h"
#include "image1.h"
#include "image2.h"

#define LCD_WIDTH 480
#define LCD_HEIGHT 480

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
    rgb_info.transfer_size = LCD_WIDTH * 80;
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
    display_info.brightness = 50;
    display_info.dma_flush_done_cb = NULL;
    display_info.user_data = &rgb_info;

    bsp_display_new_st7701(&display_if, &display_info);
    display_if->init();

    Paint_NewImage((UBYTE *)rgb_info.framebuffer1, LCD_WIDTH, LCD_HEIGHT, 0, WHITE);
    Paint_SetScale(65);

    Paint_DrawPoint(204, 9, BLACK, DOT_PIXEL_1X1, DOT_FILL_RIGHTUP);
    Paint_DrawPoint(207, 8, BLACK, DOT_PIXEL_2X2, DOT_FILL_RIGHTUP);
    Paint_DrawPoint(211, 7, BLACK, DOT_PIXEL_3X3, DOT_FILL_RIGHTUP);
    Paint_DrawPoint(216, 6, BLACK, DOT_PIXEL_4X4, DOT_FILL_RIGHTUP);
    Paint_DrawPoint(222, 5, BLACK, DOT_PIXEL_5X5, DOT_FILL_RIGHTUP);

    Paint_DrawLine(210, 20, 240, 50, MAGENTA, DOT_PIXEL_2X2, LINE_STYLE_SOLID);
    Paint_DrawLine(210, 50, 240, 20, MAGENTA, DOT_PIXEL_2X2, LINE_STYLE_SOLID);

    Paint_DrawRectangle(210, 20, 240, 50, RED, DOT_PIXEL_2X2, DRAW_FILL_EMPTY);
    Paint_DrawRectangle(245, 20, 275, 50, BLUE, DOT_PIXEL_2X2, DRAW_FILL_FULL);

    Paint_DrawLine(280, 35, 310, 35, CYAN, DOT_PIXEL_1X1, LINE_STYLE_DOTTED);
    Paint_DrawLine(295, 20, 295, 50, CYAN, DOT_PIXEL_1X1, LINE_STYLE_DOTTED);
    Paint_DrawCircle(295, 35, 15, GREEN, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);

    Paint_DrawString_EN(120, 60, "RP2350-Touch-LCD-4", &Font12, WHITE, BLUE);
    Paint_DrawString_EN(120, 75, "480x480 Pixels", &Font12, WHITE, BLACK);
    Paint_DrawString_EN(120, 90, "ST7701 Controller", &Font12, RED, WHITE);
    Paint_DrawString_EN(120, 105, "WaveShare", &Font16, RED, WHITE);
    char str[20];
    uint16_t count = 0;
    unsigned char *image_p;
    while (true)
    {
        count = (count + 1) % 1000;
        sprintf(str, "count:%04d", count);
        Paint_DrawString_EN(120, 400, str, &Font24, RED, WHITE);

        image_p = (unsigned char *)(count % 2 ? gImage_image1 : gImage_image2);
        Paint_DrawImage(image_p, 120, 120, 240, 240);
        sleep_ms(1000);
    }
}
