"""W5500 SPI 진단 스크립트 — 상세 로그 버전"""
from machine import SoftSPI, Pin
import time

MISO_PIN = 16
MOSI_PIN = 19
SCK_PIN  = 18
CS_PIN   = 17
RST_PIN  = 20

spi = SoftSPI(baudrate=100_000, polarity=1, phase=1,
              sck=Pin(SCK_PIN), mosi=Pin(MOSI_PIN), miso=Pin(MISO_PIN))
cs  = Pin(CS_PIN, Pin.OUT, value=1)
rst = Pin(RST_PIN, Pin.OUT, value=1)

print("=== W5500 진단 시작 ===")

# 1. MISO 논리 레벨 확인 (CS 없이)
miso = Pin(MISO_PIN, Pin.IN)
print("1) CS 없이 MISO 논리 레벨:", miso.value(), " (floating 이면 불규칙)")
# SoftSPI 재초기화 (Pin을 SPI가 다시 쓸 수 있게)
spi = SoftSPI(baudrate=100_000, polarity=1, phase=1,
              sck=Pin(SCK_PIN), mosi=Pin(MOSI_PIN), miso=Pin(MISO_PIN))

# 2. 하드웨어 리셋
print("2) 하드웨어 리셋 중...")
rst.value(0)
time.sleep_ms(500)
rst.value(1)
time.sleep_ms(1000)
print("   리셋 완료")

# 3. VERSION 레지스터 10회 읽기 (0x0039)
print("3) VERSIONR (0x0039) 10회 읽기:")
for i in range(10):
    cs.value(0)
    spi.write(bytes([0x00, 0x39, 0x00]))
    ver = bytearray(1)
    spi.readinto(ver)
    cs.value(1)
    time.sleep_ms(10)
    status = "OK" if ver[0] == 0x04 else "FAIL"
    print("  [{}] 0x{:02X} → {}".format(i, ver[0], status))

# 4. MR 레지스터 읽기 (0x0000)
print("4) MR (0x0000) 읽기 (정상=0x00):")
cs.value(0)
spi.write(bytes([0x00, 0x00, 0x00]))
mr = bytearray(1)
spi.readinto(mr)
cs.value(1)
print("   MR = 0x{:02X}".format(mr[0]))

# 5. 전체 공통 레지스터 덤프 (0x0000~0x000F)
print("5) 공통 레지스터 0x0000~0x000F 덤프:")
for addr in range(0x10):
    cs.value(0)
    spi.write(bytes([0x00, addr, 0x00]))
    buf = bytearray(1)
    spi.readinto(buf)
    cs.value(1)
    time.sleep_ms(2)
    print("   [{:04X}] = 0x{:02X}".format(addr, buf[0]))

print("=== 진단 완료 ===")
print("VERSION이 0x04이면 정상, 0xFF이면 MISO 미연결 또는 배선 오류")
