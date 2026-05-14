from machine import SoftSPI, Pin
import time

spi = SoftSPI(baudrate=100_000, polarity=1, phase=1,
              sck=Pin(18), mosi=Pin(19), miso=Pin(16))
cs = Pin(17, Pin.OUT, value=1)
rst = Pin(20, Pin.OUT, value=1)

def read_reg(addr):
    cs.value(0)
    spi.write(bytes([(addr >> 8) & 0xFF, addr & 0xFF, 0x00]))
    b = spi.read(1)[0]
    cs.value(1)
    return b

rst.value(0)
time.sleep_ms(300)
rst.value(1)
time.sleep_ms(1000)

print("W5500 LINK 테스트 (Pico)")
print("VERSION=0x{:02X}".format(read_reg(0x0039)))

for i in range(20):
    phy = read_reg(0x002E)
    print("{} PHYCFGR=0x{:02X} LNK={}".format(i, phy, phy & 0x01))
    time.sleep(1)
