#ifndef __MAIN_SCREEN_H__
#define __MAIN_SCREEN_H__

#include "../lvgl_ui.h"

extern lv_obj_t *ui_main_screen;

// 中文：显示时间
// English: Display time
extern lv_obj_t *label_time;
// 中文：显示日期
// English: Display date
extern lv_obj_t *label_date;
// 中文：采集电池电压的adc
// English: ADC for collecting battery voltage
extern lv_obj_t *label_battery_adc;
// 中文：电池电压
// English: Battery voltage
extern lv_obj_t *label_battery_voltage;
// 中文：芯片的温度
// English: Chip temperature
extern lv_obj_t *label_chip_temp;
// 中文：芯片的频率
// English: Chip frequency
extern lv_obj_t *label_chip_freq;
// 中文：内存大小
// English: Memory size
extern lv_obj_t *label_ram_size;
// 中文：flash 大小
// English: Flash size
extern lv_obj_t *label_flash_size;
// 中文：sd 大小
// English: SD size
extern lv_obj_t *label_sd_size;

extern lv_obj_t *label_accel_x;
extern lv_obj_t *label_accel_y;
extern lv_obj_t *label_accel_z;

extern lv_obj_t *label_gyro_x;
extern lv_obj_t *label_gyro_y;
extern lv_obj_t *label_gyro_z;

void main_screen_init(void);


#endif