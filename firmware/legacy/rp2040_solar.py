from machine import UART, Pin
import time

# ── 핀 설정 ──────────────────────────────
led  = Pin(16, Pin.OUT)
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=600)

# ── Modbus CRC16 ──────────────────────────
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

def make_read(addr, reg, count):
    req = bytes([addr, 0x03, (reg >> 8) & 0xFF, reg & 0xFF,
                 (count >> 8) & 0xFF, count & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

# ── 센서 설정 ─────────────────────────────
SENSOR_ADDR = 0x03  # 기본 0x01 → 0x03으로 변경 완료 (2026-04-24)
REQUEST     = make_read(SENSOR_ADDR, 0x0000, 1)

print("=== 조도(일사량) 센서 시작 ===")

while True:
    led.toggle()
    uart.write(REQUEST)
    time.sleep_ms(500)

    if uart.any():
        resp = uart.read()
        if len(resp) >= 5:
            solar = (resp[3] << 8) | resp[4]
            print(f"Solar:{solar} W/m2")
        else:
            print(f"응답 짧음: {resp.hex()}")
    else:
        print("응답 없음")

    time.sleep(2)
