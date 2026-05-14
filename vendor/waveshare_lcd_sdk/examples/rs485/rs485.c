#include <string.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/uart.h"

/// \tag::hello_uart[]

#define UART_ID1 uart1
#define BAUD_RATE 9600

// We are using pins 8 and 9, but see the GPIO function select table in the
// datasheet for information on which other pins can be used.
#define UART1_TX_PIN 8
#define UART1_RX_PIN 9

// const char str[] = "waveshare uart test\n";
const uint8_t dat[8] = {0x12,0x34,0x56,0x78,0x87,0x65,0x43,0x21};
const uint8_t dat_len = sizeof(dat); 
int main()
{
    stdio_init_all();
    
    uart_init(UART_ID1, BAUD_RATE);

    gpio_set_function(UART1_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART1_RX_PIN, GPIO_FUNC_UART);
    uint8_t dat_rec[8];
    uint8_t cnt = 0;
    while (1)
    {
        printf("**********************\r\n");
        printf("******TEST BEGIN******\r\n");
        printf("**********************\r\n\r\n");

        /* RS485 Receive Data*/
        for (cnt = 0; uart_is_readable(UART_ID1); cnt++)
        {
            char get = uart_getc(UART_ID1);
            dat_rec[cnt] = get;
            if (get != dat[cnt])
            {
                printf("get char = %c should =%c\r\n", get, dat[cnt]);
                break;
            }
        }
        if (cnt == dat_len)
        {
            printf("UART1 Receive success\r\n");
        }
        else
        {
            printf("UART1 Receive failure\r\n");
        }
        for (size_t i = 0; i < 8; i++)
        {
            printf("%x ",dat_rec[i]);
        }
        memset(dat_rec, 0, sizeof(dat_rec));

        /* RS485 Send Data*/
        uart_write_blocking(UART_ID1, dat, dat_len);
        printf("\nUART1 Send success\r\n");
        for (size_t i = 0; i < 8; i++)
        {
            printf("%x ",dat[i]);
        }
      
        printf("\r\n\n**********************\r\n");
        printf("*******TEST END*******\r\n");
        printf("**********************\r\n\r\n\r\n");
        
        sleep_ms(1000);
    }
}
