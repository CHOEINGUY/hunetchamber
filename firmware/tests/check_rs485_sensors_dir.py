from machine import UART, Pin
import time

led = Pin(25, Pin.OUT)
dir_pin = Pin(6, Pin.OUT, value=0)  # DE+RE tied together: 1=TX, 0=RX
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=800)

EXPECTED = [
    ("temp_humidity", 0x01, 0x03, 0x0000, 2, 9),
    ("soil_5in1",    0x02, 0x03, 0x0000, 7, 19),
    ("solar",        0x03, 0x03, 0x0000, 1, 7),
    ("co2",          0x04, 0x04, 0x0000, 1, 7),
]

def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

def make_read(addr, reg, count, fc=0x03):
    req = bytes([addr, fc, (reg >> 8) & 0xFF, reg & 0xFF,
                 (count >> 8) & 0xFF, count & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def crc_ok(resp):
    if not resp or len(resp) < 5:
        return False
    got = resp[-2] | (resp[-1] << 8)
    return got == crc16(resp[:-2])

def flush_uart():
    dir_pin.value(0)
    while uart.any():
        uart.read()
        time.sleep_ms(10)

def request(req, wait_ms=800):
    flush_uart()
    dir_pin.value(1)
    time.sleep_us(100)
    uart.write(req)
    try:
        uart.flush()
    except AttributeError:
        time.sleep_ms(10)
    dir_pin.value(0)
    time.sleep_ms(wait_ms)
    return uart.read() if uart.any() else None

def parse(name, resp):
    if not resp or not crc_ok(resp):
        return
    if name == "temp_humidity" and len(resp) >= 7:
        print("    parsed: temp={}C humidity={}%".format(
            ((resp[5] << 8) | resp[6]) / 10.0,
            ((resp[3] << 8) | resp[4]) / 10.0))
    elif name == "soil_5in1" and len(resp) >= 17:
        print("    parsed: moisture={}% temp={}C ec={} ph={} n={} p={} k={}".format(
            ((resp[3] << 8) | resp[4]) / 10.0,
            ((resp[5] << 8) | resp[6]) / 10.0,
            (resp[7] << 8) | resp[8],
            ((resp[9] << 8) | resp[10]) / 10.0,
            (resp[11] << 8) | resp[12],
            (resp[13] << 8) | resp[14],
            (resp[15] << 8) | resp[16]))
    elif name == "solar" and len(resp) >= 5:
        print("    parsed: solar={} W/m2".format((resp[3] << 8) | resp[4]))
    elif name == "co2" and len(resp) >= 5:
        print("    parsed: co2={} ppm".format((resp[3] << 8) | resp[4]))

print("=== RS485 SENSOR CHECK WITH DIR PIN ===")
print("UART0: tx=GP0 rx=GP1 baud=9600")
print("DIR: GP6 -> DE+RE, 1=TX 0=RX")

all_ok = True
for name, addr, fc, reg, count, min_len in EXPECTED:
    led.toggle()
    req = make_read(addr, reg, count, fc)
    print("\n[{}] addr=0x{:02X} fc=0x{:02X}".format(name, addr, fc))
    print("    tx:", req.hex())
    resp = request(req, 900)
    if not resp:
        print("    result: NO RESPONSE")
        all_ok = False
        continue
    ok = len(resp) >= min_len and resp[0] == addr and resp[1] == fc and crc_ok(resp)
    all_ok = all_ok and ok
    print("    rx:", resp.hex())
    print("    len={} crc_ok={} result={}".format(len(resp), crc_ok(resp), "OK" if ok else "CHECK"))
    parse(name, resp)
    time.sleep_ms(200)

print("\nEXPECTED SUMMARY:", "ALL OK" if all_ok else "CHECK FAILED")
print("=== DONE ===")
while True:
    led.toggle()
    time.sleep(1)
