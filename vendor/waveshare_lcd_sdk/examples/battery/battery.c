/**
 * Copyright (c) 2020 Raspberry Pi (Trading) Ltd.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

 
#include <stdio.h>
#include "pico/stdlib.h"
#include "bsp_battery.h"

int main()
{
    stdio_init_all();
    bsp_battery_init();
    while (true)
    {
        printf("BAT: CHRG: %d, DONE: %d\n", gpio_get(BSP_BAT_CHRG_PIN), gpio_get(BSP_BAT_DONE_PIN));
        sleep_ms(1000);
    }
}
