add_executable(rs485
    rs485.c
    )

pico_enable_stdio_usb(rs485 1)
pico_enable_stdio_uart(rs485 1)

# pull in common dependencies
target_link_libraries(rs485 
    pico_stdlib
    bsp)

# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(rs485)
