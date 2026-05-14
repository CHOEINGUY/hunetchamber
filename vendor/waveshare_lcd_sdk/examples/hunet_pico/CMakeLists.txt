add_executable(hunet_pico
    hunet_pico.c
    ../lvgl/lv_port/lv_port_disp.c
    ../lvgl/lv_port/lv_port_indev.c
)

pico_enable_stdio_usb(hunet_pico 1)
pico_enable_stdio_uart(hunet_pico 0)

target_link_libraries(hunet_pico
    pico_stdlib
    hardware_uart
    hardware_i2c
    hardware_irq
    hardware_clocks
    bsp
    lvgl
)

target_compile_definitions(hunet_pico PRIVATE
    PICO_EMBED_XIP_SETUP=1
)

pico_add_extra_outputs(hunet_pico)
