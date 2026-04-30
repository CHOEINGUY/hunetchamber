from machine import SoftSPI, Pin
import time

spi = SoftSPI(baudrate=100000, polarity=1, phase=1,
              sck=Pin(18), mosi=Pin(19), miso=Pin(16))
cs  = Pin(17, Pin.OUT)
rst = Pin(20, Pin.OUT)

rst.value(0)
time.sleep_ms(200)
rst.value(1)
time.sleep_ms(500)

cs.value(0)
spi.write(bytes([0x00, 0x39, 0x00]))
ver = spi.read(1)
cs.value(1)

print("W5500 VERSION:", hex(ver[0]))
if ver[0] == 0x04:
    print("OK - W5500 정상")
else:
    print("FAIL - 배선 확인 필요")
