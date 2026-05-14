#include "main_screen.h"
// #include "bsp_lcd_brightness.h"
#include "bsp_st7701.h"
#include "bsp_qmi8658.h"
#include "bsp_pcf85063.h"
#include "bsp_battery.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "bsp_buzzer.h"
#include "hardware/clocks.h"
#include "hardware/adc.h"
#include "bsp_sd_card.h"

uint16_t menu_cont_count = 0;

lv_obj_t *ui_main_screen = NULL;

// 中文：显示时间
// English: Display time
lv_obj_t *label_time = NULL;
// 中文：显示日期
// English: Display date
lv_obj_t *label_date = NULL;
// 中文：采集电池电压的adc
// English: ADC for collecting battery voltage
lv_obj_t *label_battery_adc = NULL;
// 中文：电池电压
// English: Battery voltage
lv_obj_t *label_battery_voltage = NULL;
// 中文：芯片的温度
// English: Chip temperature
lv_obj_t *label_chip_temp = NULL;
// 中文：芯片的频率
// English: Chip frequency
lv_obj_t *label_chip_freq = NULL;
// 中文：内存大小
// English: Memory size
lv_obj_t *label_ram_size = NULL;
// 中文：flash大小
// English: Flash size
lv_obj_t *label_flash_size = NULL;
// 中文：sd 大小
// English: SD size
lv_obj_t *label_sd_size = NULL;

lv_obj_t *label_accel_x = NULL;
lv_obj_t *label_accel_y = NULL;
lv_obj_t *label_accel_z = NULL;

lv_obj_t *label_gyro_x = NULL;
lv_obj_t *label_gyro_y = NULL;
lv_obj_t *label_gyro_z = NULL;

lv_obj_t *label_brightness = NULL;

extern bsp_display_interface_t *display_if;

typedef enum
{
    LV_MENU_ITEM_BUILDER_VARIANT_1, //
    LV_MENU_ITEM_BUILDER_VARIANT_2  //
} lv_menu_builder_variant_t;

static lv_obj_t *create_menu_text(lv_obj_t *parent, const char *icon, const char *txt,
                                  lv_menu_builder_variant_t builder_variant)
{
    // 中文：创建一个容器
    // English: Create a container
    lv_obj_t *obj = lv_menu_cont_create(parent);

    if (menu_cont_count)
        lv_obj_set_style_bg_color(obj, lv_palette_lighten(LV_PALETTE_GREEN, 1), LV_PART_MAIN);
    else
        lv_obj_set_style_bg_color(obj, lv_palette_lighten(LV_PALETTE_YELLOW, 1), LV_PART_MAIN);
    // 中文：设置背景不透明度
    // English: Set background opacity
    lv_obj_set_style_bg_opa(obj, LV_OPA_60, LV_PART_MAIN);
    menu_cont_count = (menu_cont_count + 1) % 2;

    lv_obj_t *img = NULL;
    lv_obj_t *label = NULL;
    // 中文：创建一个图片
    // English: Create a picture
    if (icon)
    {
        img = lv_img_create(obj);
        lv_img_set_src(img, icon);
    }
    // 中文：创建一个标签
    // English: Create a label
    if (txt)
    {
        label = lv_label_create(obj);
        // 中文：设置文本
        // English: Set text
        lv_label_set_text(label, txt);
        // 中文：设置文本溢出模式
        // English: Set text overflow mode
        lv_label_set_long_mode(label, LV_LABEL_LONG_SCROLL_CIRCULAR);
        // 中文：设置水平填充
        // English: Set horizontal fill
        lv_obj_set_flex_grow(label, LV_FLEX_FLOW_COLUMN);
    }
    // 中文：如果是 variant 2，则交换图片和标签
    // English: If variant 2, swap image and label
    if (builder_variant == LV_MENU_ITEM_BUILDER_VARIANT_2 && icon && txt)
    {
        lv_obj_add_flag(img, LV_OBJ_FLAG_FLEX_IN_NEW_TRACK);
        lv_obj_swap(img, label);
    }

    return obj;
}

static void create_menu_title(lv_obj_t *parent, const char *title, const lv_font_t *font)
{
    lv_obj_t *obj = lv_menu_cont_create(parent);
    // 中文：设置 Flex 布局
    // English: Set Flex layout
    lv_obj_set_flex_flow(obj, LV_FLEX_FLOW_COLUMN);                                               // 中文：纵向排列 // English: Arrange vertically
    lv_obj_set_flex_align(obj, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER); // 中文：主轴、交叉轴和内容对齐方式均居中 // English: Center alignment for main axis, cross axis, and content

    // 中文：创建标签并设置文本
    // English: Create label and set text
    lv_obj_t *label = lv_label_create(obj);
    lv_label_set_text(label, title);
    lv_obj_set_style_text_font(label, font, 0); // 中文：20号字体  // English: 20pt font
    // 中文：可选：设置标签的其他属性
    // English: Optional: Set other properties of the label
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0); // 中文：设置文本居中  // English: Set text to center
}

static void swipe_event_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_GESTURE)
    {
        lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_get_act());
        if (dir == LV_DIR_RIGHT)
        {
            lv_timer_resume(color_screen_change_timer);
            // 中文：等待触摸屏释放
            // English: Wait for the touch screen to be released
            lv_indev_wait_release(lv_indev_get_act());
            // 中文：跳转到颜色测试界面
            // English: Jump to the color test interface
            _ui_screen_change(&ui_color_screen, LV_SCR_LOAD_ANIM_FADE_ON, 500, 0, &color_screen_init);
        }
    }
}


void slider_event_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_VALUE_CHANGED)
    {
        // 中文：获取当前滑块的值
        // English: Get the current slider value
        lv_obj_t *slider = lv_event_get_target(e);
        int value = lv_slider_get_value(slider);
        // printf("Slider value: %d\n", value);
        // bsp_lcd_brightness_set(value);
        display_if->set_brightness(value);
        lv_label_set_text_fmt(label_brightness, "%d %%", value);
        // 中文：阻止事件向上传递
        // English: Stop the event from bubbling up
        lv_event_stop_bubbling(e);
    }
}

void sw_event_cb(lv_event_t * e)
{
    lv_event_code_t code = lv_event_get_code(e);
    lv_obj_t * sw = lv_event_get_target(e);

    if(code == LV_EVENT_VALUE_CHANGED) {
        bool state = lv_obj_has_state(sw, LV_STATE_CHECKED);
        bsp_buzzer_enable(state);
        printf("Switch is now %s\n", state ? "ON" : "OFF");
    }
}


// 中文：创建水平滑动条
// English: Create horizontal slider
void create_horizontal_slider(lv_obj_t *parent)
{
    // 中文：创建滑动条
    // English: Create slider
    lv_obj_t *slider = lv_slider_create(parent);

    // 中文：设置滑动条的方向为水平
    // English: Set slider direction to horizontal
    lv_slider_set_range(slider, 1, 100);          // 中文：设置滑动范围      // English: Set slider range
    lv_slider_set_value(slider, 80, LV_ANIM_OFF); // 中文：设置初始值        // English: Set initial value

    // 中文：调整滑动条大小和位置
    // English: Adjust slider size and position
    lv_obj_set_size(slider, lv_pct(85), 45);     // 中文：宽度 200，高度 20  // English: Width 200, height 20
    lv_obj_align(slider, LV_ALIGN_CENTER, 0, 0); // 中文：居中显示           // English: Center display

    lv_obj_set_style_pad_top(parent, 20, 0);
    lv_obj_set_style_pad_bottom(parent, 20, 0);
    // lv_obj_set_style_pad_left(parent, 50, 0);
    // lv_obj_set_style_pad_right(parent, 50, 0);
    lv_obj_clear_flag(parent, LV_OBJ_FLAG_GESTURE_BUBBLE);
    // 中文：添加事件回调（可选）
    // English: Add event callback (optional)
    lv_obj_add_event_cb(slider, slider_event_cb, LV_EVENT_VALUE_CHANGED, NULL);
}

// 中文：创建开关
// English: Create switch
void create_horizontal_switch(lv_obj_t *parent)
{
    // 中文：创建滑动条
    // English: Create switch
    lv_obj_t *sw = lv_switch_create(parent);

    // 中文：调整滑动条大小和位置
    // English: Adjust switch size and position
    lv_obj_set_size(sw, lv_pct(30), 45);     // 中文：宽度 200，高度 20  // English: Width 200, height 20
    lv_obj_align(sw, LV_ALIGN_CENTER, 0, 0); // 中文：居中显示           // English: Center display

    // 添加事件回调（可选）
    // English: Add event callback (optional)
    lv_obj_add_event_cb(sw, sw_event_cb, LV_EVENT_VALUE_CHANGED, NULL);
}

float read_chip_temp(void)
{
    /* 12-bit conversion, assume max value == ADC_VREF == 3.3 V */
    const float conversionFactor = 3.3f / (1 << 12);
    adc_select_input(8);
    float adc = (float)adc_read() * conversionFactor;
    float tempC = 27.0f - (adc - 0.706f) / 0.001721f;
    return tempC;
}



static void timer_1s_callback(lv_timer_t *timer)
{
    char str[15];
    struct tm now_tm;
    bsp_pcf85063_get_time(&now_tm);
    if (now_tm.tm_year >= 125 &&  now_tm.tm_year <= 130 ){
        lv_label_set_text_fmt(label_time, "%02d:%02d:%02d", now_tm.tm_hour, now_tm.tm_min, now_tm.tm_sec);
        lv_label_set_text_fmt(label_date, "%04d-%02d-%02d", now_tm.tm_year + 1900, now_tm.tm_mon + 1, now_tm.tm_mday);
    }
    
    int status = !gpio_get(BSP_BAT_CHRG_PIN);
    sprintf(str, "%s", status ? "YES" : "NO");
    lv_label_set_text(label_battery_adc, str);
    status = !gpio_get(BSP_BAT_DONE_PIN);
    sprintf(str, "%s", status ? "YES" : "NO");
    lv_label_set_text(label_battery_voltage, str);

    float chip_temp = read_chip_temp();
    sprintf(str, "%.1f C", chip_temp);
    lv_label_set_text(label_chip_temp, str);
}

static void timer_100ms_callback(lv_timer_t *timer)
{
    qmi8658_data_t data;
    bsp_qmi8658_read_data(&data);
    lv_label_set_text_fmt(label_accel_x, "%d", data.acc_x);
    lv_label_set_text_fmt(label_accel_y, "%d", data.acc_y);
    lv_label_set_text_fmt(label_accel_z, "%d", data.acc_z);
    lv_label_set_text_fmt(label_gyro_x, "%d", data.gyr_x);
    lv_label_set_text_fmt(label_gyro_y, "%d", data.gyr_y);
    lv_label_set_text_fmt(label_gyro_z, "%d", data.gyr_z);
}

void main_screen_init(void)
{
    uint32_t sys_clk = clock_get_hz(clk_sys);
    uint8_t txbuf[4] = {0x9F, 0, 0, 0}; 
    uint8_t rxbuf[4] = {0};      
    uint32_t interrupts = save_and_disable_interrupts();
    flash_do_cmd(txbuf, rxbuf, sizeof(txbuf));
    restore_interrupts(interrupts);
    uint32_t flash_size = 1 << rxbuf[3];

    ui_main_screen = lv_obj_create(NULL);
    // 中文：清除标志
    // English: Clear flags
    lv_obj_clear_flag(ui_main_screen, LV_OBJ_FLAG_SCROLLABLE); // Flags

    lv_obj_add_event_cb(ui_main_screen, swipe_event_cb, LV_EVENT_GESTURE, NULL);
    // 中文：创建菜单
    // English: Create menu
    lv_obj_t *menu = lv_menu_create(ui_main_screen);
    // 中文：获取背景颜色
    // English: Get background color
    lv_color_t bg_color = lv_obj_get_style_bg_color(menu, 0);
    // 中文：判断背景颜色是否为亮色
    // English: Check if the background color is light
    if (lv_color_brightness(bg_color) > 127)
    {
        // 中文：设置背景颜色为暗色
        // English: Set background color to dark
        lv_obj_set_style_bg_color(menu, lv_color_darken(lv_obj_get_style_bg_color(menu, 0), 10), 0);
    }
    else
    {
        // 中文：设置背景颜色为亮色
        // English: Set background color to light
        lv_obj_set_style_bg_color(menu, lv_color_darken(lv_obj_get_style_bg_color(menu, 0), 50), 0);
    }
    // 中文：设置菜单大小，宽度100%，高度100%
    // English: Set menu size, width 100%, height 100%
    lv_obj_set_size(menu, lv_pct(100), lv_pct(100));
    // 中文：居中显示
    // English: Center display
    lv_obj_center(menu);

    // 中文：创建菜单主页面
    // English: Create main menu page
    lv_obj_t *menu_main_page = lv_menu_page_create(menu, NULL);
    // 中文：隐藏滚动条
    // English: Hide scrollbar
    // lv_obj_set_style_bg_opa(menu_main_page, LV_OPA_0, LV_PART_SCROLLBAR | LV_STATE_DEFAULT);
    // 中文：滚动时隐藏滚动条
    // English: Hide scrollbar when scrolling
    // lv_obj_set_style_bg_opa(menu_main_page, LV_OPA_0, LV_PART_SCROLLBAR | LV_STATE_SCROLLED);
    // 中文：设置内边距（Margin）
    // English: Set padding (Margin)
    lv_obj_set_style_pad_top(menu_main_page, 10, 0);
    lv_obj_set_style_pad_bottom(menu_main_page, 10, 0);
    lv_obj_set_style_pad_left(menu_main_page, 50, 0);
    lv_obj_set_style_pad_right(menu_main_page, 50, 0);

    lv_obj_t *obj = NULL;
    lv_obj_t *label = NULL;
    lv_obj_t *section = NULL;

    obj = lv_menu_cont_create(menu_main_page);
    lv_obj_set_flex_flow(obj, LV_FLEX_FLOW_ROW); // 中文：水平排列子对象（可改为 LV_FLEX_FLOW_COLUMN）
    lv_obj_set_flex_align(obj, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_t *img = lv_img_create(obj);
    lv_img_set_src(img, &lv_logo_wx);

    create_menu_title(menu_main_page, "RP2350-Touch-LCD-4", &lv_font_montserrat_14);

    //------------------------------------Time and Date---------------------------------------------
    // Time and Date
    // obj = create_menu_text(menu_main_page, NULL, "Time and Date", LV_MENU_ITEM_BUILDER_VARIANT_1);
    create_menu_title(menu_main_page, "Time and Date", &lv_font_montserrat_20);

    // Create a menu section object
    section = lv_menu_section_create(menu_main_page);

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Time", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_time = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label_time, "12:00:00");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Date", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_date = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label_date, "2025-12-01");
    //--------------------------------------------------------------------------------------

    //------------------------------------Chip---------------------------------------------
    // Chip
    create_menu_title(menu_main_page, "Chip", &lv_font_montserrat_20);
    // Create a menu section object
    section = lv_menu_section_create(menu_main_page);

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "ChipType", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label = lv_label_create(obj);
    // 中文：设置值为 RP2350B
    // English: Set value to RP2350B
    lv_label_set_text(label, "RP2350B");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Temp", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_chip_temp = lv_label_create(obj);
    // 中文：设置值
    lv_label_set_text(label_chip_temp, "--- C");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Freq", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_chip_freq = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    // lv_label_set_text(label_chip_freq, "--- MHz");
    lv_label_set_text_fmt(label_chip_freq, "%d MHz", sys_clk / 1000 / 1000);
    //--------------------------------------------------------------------------------------

    //------------------------------------Memory---------------------------------------------
    // Memory
    create_menu_title(menu_main_page, "Memory", &lv_font_montserrat_20);
    // Create a menu section object
    section = lv_menu_section_create(menu_main_page);

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "RAM", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label, "520 KB");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Flash", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_flash_size = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text_fmt(label_flash_size, "%d MB", flash_size / 1024 / 1024);

    // 创建一个菜单项
    // English: Create a menu item
    // obj = create_menu_text(section, NULL, "SD", LV_MENU_ITEM_BUILDER_VARIANT_1);
    // label_sd_size = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    // lv_label_set_text_fmt(label_sd_size, "%d MB", sd_size);
    //--------------------------------------------------------------------------------------

    //------------------------------------Battery---------------------------------------------
    // Battery
    create_menu_title(menu_main_page, "Battery", &lv_font_montserrat_20);
    // Create a menu section object
    section = lv_menu_section_create(menu_main_page);

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "CHRG", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_battery_adc = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    // lv_label_set_text(label_battery_adc, "----");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "DONE", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_battery_voltage = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    // lv_label_set_text(label_battery_voltage, "--- V");
    //--------------------------------------------------------------------------------------

    //------------------------------------QMI8658---------------------------------------------
    // QMI8658
    create_menu_title(menu_main_page, "QMI8658", &lv_font_montserrat_20);
    // Create a menu section object
    section = lv_menu_section_create(menu_main_page);

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Accel_x", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_accel_x = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label_accel_x, "----");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Accel_y", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_accel_y = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label_accel_y, "----");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Accel_z", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_accel_z = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label_accel_z, "----");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Gyro_x", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_gyro_x = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label_gyro_x, "----");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Gyro_y", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_gyro_y = lv_label_create(obj);
    // 中文：设置值
    lv_label_set_text(label_gyro_y, "----");

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Gyro_z", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_gyro_z = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label_gyro_z, "----");
    //--------------------------------------------------------------------------------------

    //------------------------------------Brightness---------------------------------------------
    // Battery
    create_menu_title(menu_main_page, "Brightness", &lv_font_montserrat_20);
    // Create a menu section object
    section = lv_menu_section_create(menu_main_page);

    // 中文：创建一个菜单项
    // English: Create a menu item
    obj = create_menu_text(section, NULL, "Brightness", LV_MENU_ITEM_BUILDER_VARIANT_1);
    label_brightness = lv_label_create(obj);
    // 中文：设置值
    // English: Set value
    lv_label_set_text(label_brightness, "80 %");

    obj = lv_menu_cont_create(section);
    lv_obj_set_flex_align(obj, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    if (menu_cont_count)
        lv_obj_set_style_bg_color(obj, lv_palette_lighten(LV_PALETTE_GREEN, 1), LV_PART_MAIN);
    else
        lv_obj_set_style_bg_color(obj, lv_palette_lighten(LV_PALETTE_YELLOW, 1), LV_PART_MAIN);
    // 中文：设置背景不透明度
    // English: Set background opacity
    lv_obj_set_style_bg_opa(obj, LV_OPA_60, LV_PART_MAIN);
    menu_cont_count = (menu_cont_count + 1) % 2;
    create_horizontal_slider(obj);
    //--------------------------------------------------------------------------------------

    //------------------------------------Buzzer---------------------------------------------
    // Battery
    create_menu_title(menu_main_page, "Buzzer", &lv_font_montserrat_20);
    // Create a menu section object
    section = lv_menu_section_create(menu_main_page);

    obj = lv_menu_cont_create(section);
    lv_obj_set_flex_align(obj, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    if (menu_cont_count)
        lv_obj_set_style_bg_color(obj, lv_palette_lighten(LV_PALETTE_GREEN, 1), LV_PART_MAIN);
    else
        lv_obj_set_style_bg_color(obj, lv_palette_lighten(LV_PALETTE_YELLOW, 1), LV_PART_MAIN);
    // 中文：设置背景不透明度
    // English: Set background opacity
    lv_obj_set_style_bg_opa(obj, LV_OPA_60, LV_PART_MAIN);
    menu_cont_count = (menu_cont_count + 1) % 2;
    create_horizontal_switch(obj);
    //--------------------------------------------------------------------------------------

    //------------------------------------LOGO---------------------------------------------
    obj = lv_menu_cont_create(menu_main_page);
    // 中文：水平排列子对象（可改为 LV_FLEX_FLOW_COLUMN）
    // English: Arrange child objects horizontally
    lv_obj_set_flex_flow(obj, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(obj, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    img = lv_img_create(obj);
    lv_img_set_src(img, &lv_logo_wx);
    
    create_menu_title(menu_main_page, "RP2350-Touch-LCD-4", &lv_font_montserrat_14);
    //--------------------------------------------------------------------------------------

    lv_menu_set_page(menu, menu_main_page);
    lv_timer_create(timer_1s_callback, 1000, NULL);
    lv_timer_create(timer_100ms_callback, 100, NULL);
}
