/**
 * Copyright (c) 2020 Raspberry Pi (Trading) Ltd.
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/uart.h"
 
/// \tag::hello_serial[]

#define UART_ID uart1
#define BAUD_RATE 115200

// We are using pins 42 and 43, but see the GPIO function select table in the
// datasheet for information on which other pins can be used.
#define UART_TX_PIN 42
#define UART_RX_PIN 43

int main() {
    // Set up our UART with the required speed.
     uart_init(UART_ID, BAUD_RATE);
 
     // Set the TX and RX pins by using the function select on the GPIO
     // Set datasheet for more information on function select
     gpio_set_function(UART_TX_PIN, UART_FUNCSEL_NUM(UART_ID, UART_TX_PIN));
     gpio_set_function(UART_RX_PIN, UART_FUNCSEL_NUM(UART_ID, UART_RX_PIN));
 
    while (true) {
        uart_puts(UART_ID, "Hello, world!\n");
        sleep_ms(1000);
    }
}
