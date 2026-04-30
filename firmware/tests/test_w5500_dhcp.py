from machine import SoftSPI, Pin
import time
import wiznet5k

spi = SoftSPI(
    baudrate=100_000,
    polarity=1,
    phase=1,
    sck=Pin(26),
    mosi=Pin(3),
    miso=Pin(4),
)
cs = Pin(29, Pin.OUT)
rst = Pin(28, Pin.OUT)

rst.value(0)
time.sleep(0.5)
rst.value(1)
time.sleep(1)

print("W5500 DHCP 테스트 시작")
eth = wiznet5k.WIZNET5K(spi, cs, reset=None, is_dhcp=True, debug=True)

print("MAC:", eth.mac_address)
print("IFCONFIG:", eth.ifconfig)
print("LINK:", eth.link_status)
