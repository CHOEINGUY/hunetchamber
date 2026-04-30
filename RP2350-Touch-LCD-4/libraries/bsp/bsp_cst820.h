#ifndef __BSP_CST820_H__
#define __BSP_CST820_H__
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pico/stdlib.h"
#include "bsp_touch.h"

#define BSP_CST820_RST_PIN 16
#define BSP_CST820_INT_PIN 17

#define CST820_LCD_TOUCH_MAX_POINTS (1)

#define CST820_DEVICE_ADDR 0x15

typedef enum
{
    CST820_REG_WORK_MODE = 0x00,
    CST820_REG_READ_XY = 0x01,
    CST820_REG_DATA_START = 0x15,
    CST820_REG_PRODUCT_ID = 0xA7,
    CST820_REG_DisAutoSleep = 0xFE,
} cst820_reg_t;

bool bsp_touch_new_cst820(bsp_touch_interface_t **interface, bsp_touch_info_t *info);
bsp_touch_interface_t *bsp_cst820_get_touch_interface(void);

#endif
