add_executable(fridge_dashboard
    fridge_dashboard.c
    ../lvgl/lv_port/lv_port_disp.c
    ../lvgl/lv_port/lv_port_indev.c
)

pico_enable_stdio_usb(fridge_dashboard 1)
pico_enable_stdio_uart(fridge_dashboard 0)

target_link_libraries(fridge_dashboard
    pico_stdlib
    hardware_uart
    hardware_i2c
    hardware_irq
    hardware_clocks
    bsp
    lvgl
)

target_compile_definitions(fridge_dashboard PRIVATE
    PICO_EMBED_XIP_SETUP=1
)

pico_add_extra_outputs(fridge_dashboard)
