add_executable(lvgl_factory
    lvgl_factory.c
    ../lv_port/lv_port_disp.c
    ../lv_port/lv_port_indev.c
    )

pico_enable_stdio_usb(lvgl_factory 1)
pico_enable_stdio_uart(lvgl_factory 0)

add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/lvgl_ui)

# pull in common dependencies
target_link_libraries(lvgl_factory 
    pico_stdlib
    bsp
    lvgl_ui
    lvgl
    lvgl::demos)

target_compile_definitions(lvgl_factory PRIVATE
    PICO_EMBED_XIP_SETUP=1
)
# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(lvgl_factory)
