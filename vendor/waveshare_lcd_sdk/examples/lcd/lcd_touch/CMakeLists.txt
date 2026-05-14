add_executable(lcd_touch
    lcd_touch.c
    )

pico_enable_stdio_usb(lcd_touch 1)
pico_enable_stdio_uart(lcd_touch 0)

# pull in common dependencies
target_link_libraries(lcd_touch 
    pico_stdlib
    bsp)

# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(lcd_touch)
