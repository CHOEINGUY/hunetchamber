from machine import UART, Pin
import time

led = Pin(16, Pin.OUT)
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=800)

EXPECTED = [
    {
        "name": "temp_humidity",
        "addr": 0x01,
        "fc": 0x03,
        "reg": 0x0000,
        "count": 2,
        "min_len": 9,
    },
    {
        "name": "soil_5in1",
        "addr": 0x02,
        "fc": 0x03,
        "reg": 0x0000,
        "count": 7,
        "min_len": 19,
    },
    {
        "name": "solar",
        "addr": 0x03,
        "fc": 0x03,
        "reg": 0x0000,
        "count": 1,
        "min_len": 7,
    },
    {
        "name": "co2",
        "addr": 0x04,
        "fc": 0x04,
        "reg": 0x0000,
        "count": 1,
        "min_len": 7,
    },
]


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
    req = bytes([
        addr,
        fc,
        (reg >> 8) & 0xFF,
        reg & 0xFF,
        (count >> 8) & 0xFF,
        count & 0xFF,
    ])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def crc_ok(resp):
    if not resp or len(resp) < 5:
        return False
    got = resp[-2] | (resp[-1] << 8)
    calc = crc16(resp[:-2])
    return got == calc


def flush_uart():
    while uart.any():
        uart.read()
        time.sleep_ms(20)


def request(req, wait_ms=800):
    flush_uart()
    uart.write(req)
    time.sleep_ms(wait_ms)
    if uart.any():
        return uart.read()
    return None


def hex_bytes(data):
    return data.hex() if data else "-"


def parse_expected(sensor, resp):
    if not resp or not crc_ok(resp):
        return

    name = sensor["name"]
    if name == "temp_humidity" and len(resp) >= 7:
        humidity = ((resp[3] << 8) | resp[4]) / 10.0
        temp = ((resp[5] << 8) | resp[6]) / 10.0
        print("    parsed: temp={}C humidity={}%".format(temp, humidity))
    elif name == "soil_5in1" and len(resp) >= 17:
        moisture = ((resp[3] << 8) | resp[4]) / 10.0
        temp = ((resp[5] << 8) | resp[6]) / 10.0
        ec = (resp[7] << 8) | resp[8]
        ph = ((resp[9] << 8) | resp[10]) / 10.0
        n = (resp[11] << 8) | resp[12]
        p = (resp[13] << 8) | resp[14]
        k = (resp[15] << 8) | resp[16]
        print("    parsed: moisture={}% temp={}C ec={} ph={} n={} p={} k={}".format(
            moisture, temp, ec, ph, n, p, k
        ))
    elif name == "solar" and len(resp) >= 5:
        solar = (resp[3] << 8) | resp[4]
        print("    parsed: solar={} W/m2".format(solar))
    elif name == "co2" and len(resp) >= 5:
        co2 = (resp[3] << 8) | resp[4]
        print("    parsed: co2={} ppm".format(co2))


def check_expected():
    print("=== EXPECTED SENSOR CHECK ===")
    all_ok = True

    for sensor in EXPECTED:
        led.toggle()
        req = make_read(sensor["addr"], sensor["reg"], sensor["count"], sensor["fc"])
        print("\n[{}] addr=0x{:02X} fc=0x{:02X} reg=0x{:04X} count={}".format(
            sensor["name"], sensor["addr"], sensor["fc"], sensor["reg"], sensor["count"]
        ))
        print("    tx:", req.hex())
        resp = request(req, 900)

        if not resp:
            print("    result: NO RESPONSE")
            all_ok = False
            continue

        ok_crc = crc_ok(resp)
        ok_len = len(resp) >= sensor["min_len"]
        ok_addr = resp[0] == sensor["addr"]
        ok_fc = resp[1] == sensor["fc"]
        ok = ok_crc and ok_len and ok_addr and ok_fc
        all_ok = all_ok and ok

        print("    rx:", hex_bytes(resp))
        print("    len={} addr_ok={} fc_ok={} crc_ok={} result={}".format(
            len(resp), ok_addr, ok_fc, ok_crc, "OK" if ok else "CHECK"
        ))
        parse_expected(sensor, resp)
        time.sleep_ms(200)

    print("\nEXPECTED SUMMARY:", "ALL OK" if all_ok else "CHECK FAILED")


def scan_bus():
    print("\n=== BUS SCAN addr 0x01..0x0F ===")
    print("FC03 reg=0x0000 count=1")
    for addr in range(1, 16):
        req = make_read(addr, 0x0000, 1, 0x03)
        resp = request(req, 500)
        if resp:
            print("  FC03 addr=0x{:02X} len={} crc_ok={} rx={}".format(
                addr, len(resp), crc_ok(resp), resp.hex()
            ))
        time.sleep_ms(100)

    print("FC04 reg=0x0000 count=1")
    for addr in range(1, 16):
        req = make_read(addr, 0x0000, 1, 0x04)
        resp = request(req, 500)
        if resp:
            print("  FC04 addr=0x{:02X} len={} crc_ok={} rx={}".format(
                addr, len(resp), crc_ok(resp), resp.hex()
            ))
        time.sleep_ms(100)


print("=== RS485 SENSOR CHECK ===")
print("UART0: tx=GP0 rx=GP1 baud=9600")
print("Expected: temp/humidity=0x01, soil=0x02, solar=0x03, co2=0x04")
print("If all sensors fail, check A/B, power, and common GND.")

check_expected()
scan_bus()

print("\n=== DONE ===")
while True:
    led.toggle()
    time.sleep(1)
