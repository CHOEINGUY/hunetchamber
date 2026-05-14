from machine import Pin, UART
import time


uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=100)


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


def make_read(addr, reg, count, fc=0x03):
    req = bytes([addr, fc, (reg >> 8) & 0xFF, reg & 0xFF,
                 (count >> 8) & 0xFF, count & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def read_addr(addr):
    while uart.any():
        uart.read()
    uart.write(make_read(addr, 0x0000, 2))
    time.sleep_ms(300)
    resp = uart.read() if uart.any() else None
    if not resp:
        return None
    if len(resp) < 7:
        return ("short", resp)
    body = resp[:-2]
    got_crc = resp[-2] | (resp[-1] << 8)
    if crc16(body) != got_crc:
        return ("bad_crc", resp)
    if resp[0] != addr:
        return ("wrong_addr", resp)
    if resp[1] != 0x03:
        return ("wrong_fc", resp)
    humidity = ((resp[3] << 8) | resp[4]) / 10.0
    raw_temp = (resp[5] << 8) | resp[6]
    if raw_temp & 0x8000:
        raw_temp -= 0x10000
    temp = raw_temp / 10.0
    return ("ok", temp, humidity, resp)


print("=== RS485 temp/humidity address scan ===")
print("UART0 GP0=TX GP1=RX baud=9600")
print("Connect ONE sensor first. Scanning 1..20.")

while True:
    found = 0
    for addr in range(1, 21):
        result = read_addr(addr)
        if result is None:
            print("addr {:02d}: no response".format(addr))
        elif result[0] == "ok":
            found += 1
            print("addr {:02d}: OK temp={:.1f}C humidity={:.1f}% raw={}".format(
                addr, result[1], result[2], result[3]
            ))
        else:
            print("addr {:02d}: {} raw={}".format(addr, result[0], result[1]))
        time.sleep_ms(80)
    print("scan done, found={}".format(found))
    time.sleep(2)
