from machine import UART, Pin
import time

led = Pin(25, Pin.OUT)
relay = Pin(2, Pin.OUT, value=1)  # active-low relay: 1=OFF, 0=ON
relay_state = 0

def set_relay(cmd):
    global relay_state
    relay_state = cmd & 0x01
    relay.value(0 if relay_state else 1)

# Temporary RP2350 link test.
# Reuse the existing sensor RS485-TTL module, but move its TTL side to:
#   Pico GP4(TX) -> module DI/RX
#   Pico GP5(RX) <- module RO/TX
#   Pico GND     -> module GND
# And connect module A/B to RP2350 RS485 A/B.
display_uart = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5), timeout=20)

print("=== RP2350 RS485 display link test ===")

i = 0
while True:
    led.toggle()
    air_temp = 24.0 + (i % 10) * 0.1
    humidity = 35.0 + (i % 20) * 0.2
    moisture = 40.0 + (i % 5)
    soil_temp = 23.0 + (i % 8) * 0.1
    ec = 70 + (i % 10)
    ph = 6.5 + (i % 4) * 0.1
    n = 3
    p = 5
    k = 13
    solar = 3 + (i % 3)
    co2 = 850 + (i % 30)

    msg = "{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
        air_temp, humidity, moisture, soil_temp, ec, ph,
        n, p, k, solar, co2, relay_state
    )

    while display_uart.any():
        display_uart.read()

    display_uart.write(msg.encode())
    time.sleep_ms(30)

    if display_uart.any():
        cmd = display_uart.read(1)
        if cmd:
            set_relay(cmd[0])
            print("relay cmd:", relay_state, "pin:", relay.value())

    print("sent:", msg.strip())
    i += 1
    time.sleep(1)
