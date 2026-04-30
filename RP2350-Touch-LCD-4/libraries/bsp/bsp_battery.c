#include "bsp_battery.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"

#define BATTERY_ADC_SIZE 9

// 中文：排序函数（冒泡排序实现，可根据需要替换为其他排序算法）
// English: Sorting function (implemented by bubble sort, can be replaced by other sorting algorithms as needed)
static void bubble_sort(uint16_t *data, uint16_t size)
{
    for (uint8_t i = 0; i < size - 1; i++)
    {
        for (uint8_t j = 0; j < size - i - 1; j++)
        {
            if (data[j] > data[j + 1])
            {
                uint16_t temp = data[j];
                data[j] = data[j + 1];
                data[j + 1] = temp;
            }
        }
    }
}

static uint16_t average_filter(uint16_t *samples)
{
    uint16_t out;
    bubble_sort(samples, BATTERY_ADC_SIZE);
    for (int i = 1; i < BATTERY_ADC_SIZE - 1; i++)
    {
        out += samples[i] / (BATTERY_ADC_SIZE - 2);
    }
    return out;
}

uint16_t bsp_battery_read_raw(void)
{
    uint16_t samples[BATTERY_ADC_SIZE];
    adc_select_input(BSP_BAT_ADC_PIN - 40);
    for (int i = 0; i < BATTERY_ADC_SIZE; i++)
    {
        samples[i] = adc_read();
    }
    // 中文：用中位值滤波
    // English: Use median filtering
    return average_filter(samples); 
}

void bsp_battery_read(float *voltage, uint16_t *adc_raw)
{
    uint16_t result = bsp_battery_read_raw();
    if (adc_raw)
    {
        *adc_raw = result;
    }
    if (voltage)
    {
        *voltage = result * (3.3 / (1 << 12)) * 3.0;
    }
}

void bsp_battery_init(void)
{
    adc_init();
    // adc_gpio_init(BSP_BAT_ADC_PIN);
    gpio_init(BSP_BAT_CHRG_PIN);
    gpio_init(BSP_BAT_DONE_PIN);
    gpio_set_dir(BSP_BAT_CHRG_PIN, GPIO_IN);
    gpio_set_dir(BSP_BAT_DONE_PIN, GPIO_IN);
    gpio_pull_up(BSP_BAT_CHRG_PIN);
    gpio_pull_up(BSP_BAT_DONE_PIN);
}
