add_executable(lvgl_pcf85063
    lvgl_pcf85063.c
    ../lv_port/lv_port_disp.c
    ../lv_port/lv_port_indev.c
    )

pico_enable_stdio_usb(lvgl_pcf85063 1)
pico_enable_stdio_uart(lvgl_pcf85063 0)

# pull in common dependencies
target_link_libraries(lvgl_pcf85063 
    pico_stdlib
    bsp
    lvgl
    lvgl::demos)

target_compile_definitions(lvgl_pcf85063 PRIVATE
    PICO_EMBED_XIP_SETUP=1
)
# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(lvgl_pcf85063)
