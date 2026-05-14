add_executable(lcd_image
    lcd_image.c
    )

pico_enable_stdio_usb(lcd_image 1)
pico_enable_stdio_uart(lcd_image 0)

# pull in common dependencies
target_link_libraries(lcd_image 
    pico_stdlib
    bsp)

target_compile_definitions(lcd_image PRIVATE
    PICO_EMBED_XIP_SETUP=1
)
# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(lcd_image)
