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

def make_request(addr):
    req = bytes([addr, 0x03, 0x00, 0x00, 0x00, 0x07])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

# ── 센서 설정 ─────────────────────────────
SENSOR_ADDR = 0x02  # 0x01 → 0x02로 변경 완료 (2026-04-24)
REQUEST     = make_request(SENSOR_ADDR)

print("=== 토양 5 in 1 센서 시작 ===")

while True:
    led.toggle()
    uart.write(REQUEST)
    time.sleep_ms(600)

    if uart.any():
        resp = uart.read()
        if len(resp) >= 17:
            moisture = ((resp[3]  << 8) | resp[4])  / 10.0
            temp     = ((resp[5]  << 8) | resp[6])  / 10.0
            ec       = (resp[7]   << 8) | resp[8]
            ph       = ((resp[9]  << 8) | resp[10]) / 10.0
            n        = (resp[11]  << 8) | resp[12]
            p        = (resp[13]  << 8) | resp[14]
            k        = (resp[15]  << 8) | resp[16]
            print(f"Moisture:{moisture}% | Temp:{temp}C | EC:{ec} | pH:{ph} | N:{n} P:{p} K:{k}")
        else:
            print(f"응답 짧음: {resp.hex()}")
    else:
        print("응답 없음")

    time.sleep(2)
