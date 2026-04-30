#include <stdio.h>
#include "pico/stdlib.h"
#include "bsp_i2c.h"
#include "bsp_qmi8658.h"

int main()
{
    qmi8658_data_t data;
    stdio_init_all();
    bsp_i2c_init();
    bsp_qmi8658_init();

    while (true)
    {
        bsp_qmi8658_read_data(&data);
        printf("acc: %5d %5d %5d , gyr:%5d %5d %5d\r\n", data.acc_x, data.acc_y, data.acc_z, data.gyr_x, data.gyr_y, data.gyr_z);
        sleep_ms(50);
    }
}
