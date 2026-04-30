from machine import SoftSPI, Pin
import time
import wiznet5k

spi = SoftSPI(
    baudrate=100_000,
    polarity=1,
    phase=1,
    sck=Pin(18),
    mosi=Pin(19),
    miso=Pin(16),
)
cs = Pin(17, Pin.OUT)
rst = Pin(20, Pin.OUT)

rst.value(0)
time.sleep(0.5)
rst.value(1)
time.sleep(1)

print("W5500 DHCP 테스트 시작 (Pico)")
eth = wiznet5k.WIZNET5K(spi, cs, reset=None, is_dhcp=True, debug=False)

print("MAC:", eth.mac_address)
print("IFCONFIG:", eth.ifconfig)
for i in range(10):
    phy = eth.read(0x002E, 0x00)[0]
    print("PHYCFGR=0x{:02X} LNK={}".format(phy, phy & 0x01))
    time.sleep(1)
