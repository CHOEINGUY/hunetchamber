/**
 * Copyright (c) 2020 Raspberry Pi (Trading) Ltd.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include <stdio.h>
#include "pico/stdlib.h"
#include "bsp_xl2515.h"

int main()
{
    // set_cpu_clock(240);
    uint32_t send_id = 0x123;
    uint32_t rec_id = 0;
    uint8_t len;
    uint8_t data[8] = {0x12, 0x34, 0x56, 0x78, 0x87, 0x65, 0x43, 0x21};
    stdio_init_all();
    bsp_xl2515_init(KBPS5);
    while (true) {
        printf("Hello world!\n");
        if (bsp_xl2515_recv(&rec_id, data, &len))
        {
            printf("recv id: 0x%x, len: %d  data: ", rec_id, len);
            for (size_t i = 0; i < len; i++)
            {
                printf("0x%2x ", data[i]);
            }
            printf("\r\n");
        }
        bsp_xl2515_send(send_id, data, 8);
        sleep_ms(1000);
    }
}
