if (TARGET tinyusb_device)
    add_executable(battery
            battery.c
            )

    # pull in common dependencies
    target_link_libraries(battery pico_stdlib bsp)

    # enable usb output, disable uart output
    pico_enable_stdio_usb(battery 1)
    pico_enable_stdio_uart(battery 0)

    # create map/bin/hex/uf2 file etc.
    pico_add_extra_outputs(battery)

    # add url via pico_set_program_url
    # example_auto_set_url(battery)
elseif(PICO_ON_DEVICE)
    message("Skipping battery because TinyUSB submodule is not initialized in the SDK")
endif()
