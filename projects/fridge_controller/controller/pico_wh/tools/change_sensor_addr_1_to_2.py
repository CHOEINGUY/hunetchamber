from machine import UART, Pin
import time


uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=120)


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


def make_write(addr, reg, value):
    req = bytes([addr, 0x06, (reg >> 8) & 0xFF, reg & 0xFF,
                 (value >> 8) & 0xFF, value & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def transact(req, wait_ms=350):
    while uart.any():
        uart.read()
    uart.write(req)
    try:
        uart.flush()
    except AttributeError:
        time.sleep_ms(20)
    time.sleep_ms(wait_ms)
    return uart.read() if uart.any() else None


def read_temp(addr):
    resp = transact(make_read(addr, 0x0000, 2), 350)
    if not resp or len(resp) < 9:
        return None, resp
    body = resp[:-2]
    got_crc = resp[-2] | (resp[-1] << 8)
    if crc16(body) != got_crc or resp[0] != addr or resp[1] != 0x03:
        return None, resp
    humidity = ((resp[3] << 8) | resp[4]) / 10.0
    temp = ((resp[5] << 8) | resp[6]) / 10.0
    return (temp, humidity), resp


def write_addr_1_to_2():
    req = make_write(0x01, 0x07D0, 0x0002)
    print("write addr 1 -> 2:", req)
    resp = transact(req, 500)
    print("write resp:", resp)
    if resp and resp == req:
        print("write echo OK")
    elif resp:
        print("write echo CHECK")
    else:
        print("write no response")


print("=== Change temp/humidity sensor addr 1 -> 2 ===")
print("IMPORTANT: connect only the new sensor.")

before, raw = read_temp(0x01)
print("before addr01:", before, raw)

write_addr_1_to_2()
time.sleep(1)

after1, raw1 = read_temp(0x01)
after2, raw2 = read_temp(0x02)
print("after addr01:", after1, raw1)
print("after addr02:", after2, raw2)

print("done")
