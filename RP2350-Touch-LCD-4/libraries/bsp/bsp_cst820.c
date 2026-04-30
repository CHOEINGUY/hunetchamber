#include "bsp_cst820.h"
#include "bsp_i2c.h"

static bsp_touch_info_t *g_touch_info;
static bsp_touch_interface_t *g_touch_if;
static bool g_cst820_irq_flag = false;

bsp_touch_interface_t *bsp_cst820_get_touch_interface(void)
{
    return g_touch_if;
}

void bsp_cst820_reg_read_byte(uint8_t reg_addr, uint8_t *data, size_t len)
{
    bsp_i2c_read_reg8(CST820_DEVICE_ADDR, reg_addr, data, len);
}

void bsp_cst820_reg_write_byte(uint8_t reg_addr, uint8_t *data, size_t len)
{
    bsp_i2c_write_reg8(CST820_DEVICE_ADDR, reg_addr, data, len);
}

static void bsp_cst820_get_rotation(uint16_t *rotation)
{
    *rotation = g_touch_info->rotation;
}

static void bsp_cst820_set_rotation(uint16_t rotation)
{
    uint16_t swap;

    if (rotation == 1 || rotation == 3)
    {
        if (g_touch_info->width < g_touch_info->height)
        {
            swap = g_touch_info->width;
            g_touch_info->width = g_touch_info->height;
            g_touch_info->height = swap;
        }
    }
    else
    {
        if (g_touch_info->width > g_touch_info->height)
        {
            swap = g_touch_info->width;
            g_touch_info->width = g_touch_info->height;
            g_touch_info->height = swap;
        }
    }
    g_touch_info->rotation = rotation;
}

static bool bsp_cst820_get_touch_data(bsp_touch_data_t *data)
{
    
    if (g_touch_info->data.points == 0 || data == NULL)
        return false;

    data->points = g_touch_info->data.points;
    for (int i = 0; i < data->points; i++)
    {
        switch (g_touch_info->rotation)
        {
        case 1:
            data->coords[i].x = g_touch_info->data.coords[i].y;
            data->coords[i].y = g_touch_info->height - 1 - g_touch_info->data.coords[i].x;
            break;
        case 2:
            data->coords[i].x = g_touch_info->width - 1 - g_touch_info->data.coords[i].x;
            data->coords[i].y = g_touch_info->height - 1 - g_touch_info->data.coords[i].y;
            break;
        case 3:
            data->coords[i].x = g_touch_info->width - g_touch_info->data.coords[i].y;
            data->coords[i].y = g_touch_info->data.coords[i].x;
            break;
        default:
            data->coords[i].x = g_touch_info->data.coords[i].x;
            data->coords[i].y = g_touch_info->data.coords[i].y;
            break;
        }
        data->coords[i].pressure = g_touch_info->data.coords[i].pressure;
    }
    return true;
}

void bsp_cst820_read(void)
{
    uint8_t buffer[12];
    if (g_cst820_irq_flag == false)
    {
        g_touch_info->data.points = 0;
        return;
    }
    g_cst820_irq_flag = false;

    bsp_cst820_reg_read_byte(CST820_REG_READ_XY, buffer, 6);
    g_touch_info->data.points = buffer[1] & 0x0F;
    if(g_touch_info->data.points>CST820_LCD_TOUCH_MAX_POINTS)g_touch_info->data.points=CST820_LCD_TOUCH_MAX_POINTS;
    for (int i = 0; i < g_touch_info->data.points; i++)
    {
        g_touch_info->data.coords[i].x = ((uint16_t)(buffer[(i * 6) + 2] & 0x0F) << 8) + buffer[(i * 6) + 3];
        g_touch_info->data.coords[i].y = ((uint16_t)(buffer[(i * 6) + 4] & 0x0F) << 8) + buffer[(i * 6) + 5];
    }
}

static void touch_irq_callbac(uint gpio, uint32_t event_mask)
{
    if (event_mask == GPIO_IRQ_EDGE_FALL)
    {
        g_cst820_irq_flag = true;
    }
}

void bsp_cst820_reset(void)
{
    gpio_put(BSP_CST820_RST_PIN, 0);
    sleep_ms(20);
    gpio_put(BSP_CST820_RST_PIN, 1);
    sleep_ms(150);
}

void bsp_cst820_init(void)
{
    uint8_t buffer[6];
    gpio_init(BSP_CST820_RST_PIN);
    gpio_set_dir(BSP_CST820_RST_PIN, GPIO_OUT);

    gpio_init(BSP_CST820_INT_PIN);
    gpio_set_dir(BSP_CST820_INT_PIN, GPIO_IN);
    gpio_pull_up(BSP_CST820_INT_PIN);
    
    bsp_cst820_reset();
    buffer[0] = 0x01;
    bsp_cst820_reg_write_byte(CST820_REG_DATA_START, buffer, 1);
    sleep_ms(100);
    buffer[0] = 0xFF;
    bsp_cst820_reg_write_byte(CST820_REG_DisAutoSleep, buffer, 1);
    buffer[0] = 0x00;
    bsp_cst820_reg_write_byte(CST820_REG_WORK_MODE, buffer, 1);
    do
    {
        bsp_cst820_reg_read_byte(CST820_REG_PRODUCT_ID, buffer, 1);
        if (buffer[0] == 0xb7)
        {
            printf("CST820 ID:0x%2x\r\n", buffer[0]);
            break;
        }
        else
            printf("Not found CST820!!\r\n");
        sleep_ms(1000);
    } while (1);

    gpio_set_irq_enabled_with_callback(BSP_CST820_INT_PIN, GPIO_IRQ_EDGE_FALL, true, touch_irq_callbac);
}

bool bsp_touch_new_cst820(bsp_touch_interface_t **interface, bsp_touch_info_t *info)
{
    if (info == NULL)
        return false;

    static bsp_touch_interface_t touch_if;
    static bsp_touch_info_t touch_info;

    memcpy(&touch_info, info, sizeof(bsp_touch_info_t));

    touch_if.init = bsp_cst820_init;
    touch_if.reset = bsp_cst820_reset;
    touch_if.read = bsp_cst820_read;
    touch_if.get_data = bsp_cst820_get_touch_data;
    touch_if.get_rotation = bsp_cst820_get_rotation;
    touch_if.set_rotation = bsp_cst820_set_rotation;

    g_touch_if = &touch_if;
    *interface = &touch_if;
    g_touch_info = &touch_info;
    return true;
}
