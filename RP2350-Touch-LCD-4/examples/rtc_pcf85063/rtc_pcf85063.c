#include <stdio.h>
#include "pico/stdlib.h"
#include "bsp_i2c.h"
#include "bsp_pcf85063.h"

int main()
{
    struct tm now_tm;
    stdio_init_all();
    bsp_i2c_init();
    bsp_pcf85063_init();
    
    bsp_pcf85063_get_time(&now_tm);

    if (now_tm.tm_year < 124 || now_tm.tm_year > 130 )
    {
        now_tm.tm_year = 2024 - 1900; // The year starts from 1900
        now_tm.tm_mon = 11 - 1;       // Months start from 0 (November = 10)
        now_tm.tm_mday = 22;          // Day of the month
        now_tm.tm_hour = 12;          // Hour
        now_tm.tm_min = 0;            // Minute
        now_tm.tm_sec = 0;            // Second
        now_tm.tm_isdst = -1;         // Automatically detect daylight saving time
        bsp_pcf85063_set_time(&now_tm);
    }

    while (1)
    {
        bsp_pcf85063_get_time(&now_tm);
        printf("time: %s\n", asctime(&now_tm));
        sleep_ms(1000);
    }
}
