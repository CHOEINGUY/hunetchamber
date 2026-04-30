add_executable(gui
    gui.c
    )

pico_enable_stdio_usb(gui 1)
pico_enable_stdio_uart(gui 0)

# pull in common dependencies
target_link_libraries(gui 
    GUI
    Fonts
    pico_stdlib
    bsp)

target_compile_definitions(gui PRIVATE
    PICO_EMBED_XIP_SETUP=1
)
# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(gui)
