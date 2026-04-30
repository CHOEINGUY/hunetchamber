from machine import UART, Pin
import time

led  = Pin(16, Pin.OUT)
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=600)

def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

def make_read(addr, reg, count, fc=0x04):
    req = bytes([addr, fc, (reg >> 8) & 0xFF, reg & 0xFF,
                 (count >> 8) & 0xFF, count & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def make_write(addr, reg, value):
    req = bytes([addr, 0x06, (reg >> 8) & 0xFF, reg & 0xFF,
                 (value >> 8) & 0xFF, value & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

# 현재 센서 주소 (공장 기본값 0x01, 변경 후 0x04로 수정)
SENSOR_ADDR = 0x01
REQUEST     = make_read(SENSOR_ADDR, 0x0000, 1)

print("=== CO2 센서 단독 테스트 (9600 baud, addr=0x01) ===")
print("주소 변경이 필요하면 change_addr() 함수 참고")
print("웜업 최대 180초 소요")

# 주소 변경 방법 (필요시 REPL에서 직접 실행):
# uart.write(make_write(0x01, 0x0200, 0x04))  # addr 0x01 → 0x04
# time.sleep_ms(500)
# print(uart.read())  # 응답 확인 후 전원 재인가

print("=== 버스 전체 주소 스캔 (FC=03, 0x00~0x0F) ===")
for addr in range(0x00, 0x10):
    uart.read()
    req = make_read(addr, 0x0000, 1)
    uart.write(req)
    time.sleep_ms(800)
    resp = uart.read()
    if resp:
        print(f"FC03 addr=0x{addr:02X} 응답: {resp.hex()}")
    time.sleep_ms(100)

print("=== FC=04로 재스캔 ===")
for addr in range(0x00, 0x10):
    uart.read()
    req = make_read(addr, 0x0000, 1, fc=0x04)
    uart.write(req)
    time.sleep_ms(800)
    resp = uart.read()
    if resp:
        print(f"FC04 addr=0x{addr:02X} 응답: {resp.hex()}")
    time.sleep_ms(100)

print("스캔 완료")
while True:
    pass
