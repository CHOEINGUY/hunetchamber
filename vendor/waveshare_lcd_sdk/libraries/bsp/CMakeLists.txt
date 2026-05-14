# Search for all source files in the current directory
# and save the names to the DIR_BSP_SRCS variable
aux_source_directory(. DIR_BSP_SRCS)

# Generate link library
add_library(bsp ${DIR_BSP_SRCS})

# Add the standard include files to the build
target_include_directories(bsp PUBLIC
  ${CMAKE_CURRENT_LIST_DIR}
)

# pico_generate_pio_header(bsp ${CMAKE_CURRENT_LIST_DIR}/bsp_i2s.pio)
# pico_generate_pio_header(bsp ${CMAKE_CURRENT_LIST_DIR}/st7701_rgb.pio)
pico_generate_pio_header(bsp ${CMAKE_CURRENT_LIST_DIR}/pio_rgb.pio)

target_link_libraries(bsp PUBLIC 
    pico_stdlib 
    hardware_spi 
    hardware_i2c 
    hardware_pwm 
    hardware_adc 
    hardware_dma
    hardware_pio
    hardware_irq
    no-OS-FatFS-SD-SDIO-SPI-RPi-Pico
  )
