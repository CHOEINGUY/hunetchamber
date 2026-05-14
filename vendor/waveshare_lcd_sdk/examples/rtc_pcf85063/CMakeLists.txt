add_executable(rtc_pcf85063
    rtc_pcf85063.c
    )

pico_enable_stdio_usb(rtc_pcf85063 1)
pico_enable_stdio_uart(rtc_pcf85063 0)

# pull in common dependencies
target_link_libraries(rtc_pcf85063 
    pico_stdlib
    bsp)

# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(rtc_pcf85063)
