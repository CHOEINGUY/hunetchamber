add_executable(qmi8658_raw_out
    qmi8658_raw_out.c
    )

pico_enable_stdio_usb(qmi8658_raw_out 1)
pico_enable_stdio_uart(qmi8658_raw_out 0)

# pull in common dependencies
target_link_libraries(qmi8658_raw_out 
    pico_stdlib
    bsp)

# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(qmi8658_raw_out)
