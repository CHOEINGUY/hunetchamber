add_executable(sd_card_sdio
    sd_card_sdio.c
    )

pico_enable_stdio_usb(sd_card_sdio 1)
pico_enable_stdio_uart(sd_card_sdio 0)

# pull in common dependencies
target_link_libraries(sd_card_sdio 
    pico_stdlib
    bsp)

# create map/bin/hex/uf2 file etc.
pico_add_extra_outputs(sd_card_sdio)
