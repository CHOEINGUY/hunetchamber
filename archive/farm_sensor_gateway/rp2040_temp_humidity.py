from machine import UART, Pin
import time

# ── 핀 설정 ──────────────────────────────
led  = Pin(16, Pin.OUT)
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=500)

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

def make_request(addr):
    req = bytes([addr, 0x03, 0x00, 0x00, 0x00, 0x02])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

# ── 센서 설정 ─────────────────────────────
SENSOR_ADDR = 0x01
REQUEST     = make_request(SENSOR_ADDR)

print("=== 온습도 센서 시작 ===")

while True:
    led.toggle()
    uart.write(REQUEST)
    time.sleep_ms(500)

    if uart.any():
        resp = uart.read()
        if len(resp) >= 7:
            humidity    = ((resp[3] << 8) | resp[4]) / 10.0
            temperature = ((resp[5] << 8) | resp[6]) / 10.0
            print(f"Temp: {temperature}C | Humidity: {humidity}%")
        else:
            print(f"응답 짧음: {resp.hex()}")
    else:
        print("응답 없음")

    time.sleep(2)
