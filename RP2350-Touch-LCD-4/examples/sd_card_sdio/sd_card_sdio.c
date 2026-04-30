#include <stdio.h>
#include "pico/stdlib.h"
#include "bsp_sd_card.h"

int main()
{
    stdio_init_all();
    sleep_ms(3000);
    uint32_t sd_card_size;
    if (bsp_sd_card_init())
    {
        bsp_sd_card_test();
        sd_card_size = bsp_sd_card_get_size();
        printf("SD card init success, size: %d MB\n", sd_card_size);
    }
    else
    {
        printf("SD card init failed\n");
    }
    while (1)
    {
        sleep_ms(1000);
    }
    
}
