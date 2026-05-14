add_executable(can
    can.c
    )

pico_enable_stdio_usb(can 1)
pico_enable_stdio_uart(can 0)

# pull in common dependencies
target_link_libraries(can 
    pico_stdlib
    bsp)

# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(can)
