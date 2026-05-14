
    add_executable(buzzer
            buzzer.c
            )

    # pull in common dependencies
    target_link_libraries(buzzer pico_stdlib bsp)

    # enable usb output, disable uart output
    pico_enable_stdio_usb(buzzer 1)
    pico_enable_stdio_uart(buzzer 0)

    # create map/bin/hex/uf2 file etc.
    pico_add_extra_outputs(buzzer)

    # add url via pico_set_program_url
    # example_auto_set_url(buzzer)
    