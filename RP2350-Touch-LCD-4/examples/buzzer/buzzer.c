/**
 * Copyright (c) 2020 Raspberry Pi (Trading) Ltd.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include <stdio.h>
#include "pico/stdlib.h"
#include "bsp_buzzer.h"

int main() {
    stdio_init_all();
    bsp_buzzer_init();
    while (true) {
        bsp_buzzer_enable(true);
        sleep_ms(1000);
        bsp_buzzer_enable(false);
        sleep_ms(1000);
    }
}
