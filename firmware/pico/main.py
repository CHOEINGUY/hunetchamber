import json
import wiznet5k
import wiznet5k_socket as socket
from machine import UART, Pin, SPI, SoftI2C
import time

# ── 핀 설정 ──────────────────────────────────────────
led   = Pin(25, Pin.OUT)          # Pico 온보드 LED
relay = Pin(2, Pin.OUT, value=0)
uart  = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=600)

# ── RP2350 디스플레이 I2C 마스터 ──────────────────────
# GP6(SDA) / GP7(SCL) → RP2350 GP6/GP7 (I2C1 슬레이브 0x42)
i2c_disp = SoftI2C(sda=Pin(6), scl=Pin(7), freq=100_000)
DISP_ADDR = 0x42

def send_to_display(d):
    msg = "{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
        d.get('air_temp',  0),
        d.get('humidity',  0),
        d.get('moisture',  0),
        d.get('soil_temp', 0),
        d.get('ec',        0),
        d.get('ph',        0),
        d.get('n',         0),
        d.get('p',         0),
        d.get('k',         0),
        d.get('solar',     0),
        d.get('co2',       0),
        d.get('relay',     0),
    )
    try:
        i2c_disp.writeto(DISP_ADDR, msg.encode())
    except Exception as e:
        print("I2C disp 오류:", e)

# ── W5500 하드웨어 SPI 설정 ──────────────────────────
# Pico 표준 SPI0 핀: SCK=GP18, MOSI=GP19, MISO=GP16
spi = SPI(0, baudrate=1_000_000, polarity=1, phase=1,
          sck=Pin(18), mosi=Pin(19), miso=Pin(16))
cs  = Pin(17, Pin.OUT)
rst = Pin(20, Pin.OUT)

# ── W5500 네트워크 초기화 ─────────────────────────────
def init_network():
    rst.value(0)
    time.sleep(0.5)
    rst.value(1)
    time.sleep(1)

    print("W5500 초기화...")
    nic = wiznet5k.WIZNET5K(spi, cs, reset=None, is_dhcp=True)
    socket.set_interface(nic)

    print("PHY 재설정 중...")
    nic.write(0x002E, 0x04, 0x78)
    time.sleep(0.1)
    nic.write(0x002E, 0x04, 0xF8)
    time.sleep(3)

    for i in range(10):
        phycfgr = nic.read(0x002E, 0x00)[0]
        lnk = phycfgr & 0x01
        print("  {}초: PHYCFGR=0x{:02X} LNK={}".format(i + 1, phycfgr, lnk))
        if lnk:
            print("링크 UP")
            break
        time.sleep(1)

    wiznet5k.WIZNET5K.link_status = property(lambda self: 1)
    print("DHCP 설정 완료:", nic.ifconfig)
    return nic

# ── HTTP POST ─────────────────────────────────────────
SERVER_IP   = '192.168.100.30'
SERVER_PORT = 8080
SERVER_PATH = '/sensor'
HTTP_TIMEOUT_SECONDS = 2
LOOP_SLEEP_MS = 500

def http_post(data: dict):
    body = json.dumps(data)
    request = (
        f"POST {SERVER_PATH} HTTP/1.1\r\n"
        f"Host: {SERVER_IP}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )
    try:
        s = socket.socket()
        s.settimeout(HTTP_TIMEOUT_SECONDS)
        s.connect((SERVER_IP, SERVER_PORT))
        s.send(request.encode())
        s.close()
        return True
    except Exception as e:
        print("HTTP 전송 오류:", e)
        return False

# ── Modbus ───────────────────────────────────────────
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

def read_sensor(req, wait_ms=300):
    while uart.any():
        uart.read()
    uart.write(req)
    time.sleep_ms(wait_ms)
    return uart.read() if uart.any() else None

# ── 센서 요청 패킷 ────────────────────────────────────
REQ_TH    = make_read(0x01, 0x0000, 2)
REQ_SOIL  = make_read(0x02, 0x0000, 7)
REQ_SOLAR = make_read(0x03, 0x0000, 1)
REQ_CO2   = make_read(0x04, 0x0000, 1, fc=0x04)

# ── 메인 ─────────────────────────────────────────────
print("=== Hunet 통합 센서 시작 (Pico) ===")
nic = init_network()
fail_count = 0

while True:
    led.toggle()

    resp_th    = read_sensor(REQ_TH, 250)
    time.sleep_ms(50)
    resp_soil  = read_sensor(REQ_SOIL, 350)
    time.sleep_ms(50)
    resp_solar = read_sensor(REQ_SOLAR, 250)
    time.sleep_ms(50)
    resp_co2   = read_sensor(REQ_CO2, 450)

    data = {}

    if resp_th and len(resp_th) >= 9:
        data['humidity']  = ((resp_th[3] << 8) | resp_th[4]) / 10.0
        data['air_temp']  = ((resp_th[5] << 8) | resp_th[6]) / 10.0
        relay.value(1 if data['air_temp'] > 30 else 0)

    if resp_soil and len(resp_soil) >= 17:
        data['moisture']  = ((resp_soil[3]  << 8) | resp_soil[4])  / 10.0
        data['soil_temp'] = ((resp_soil[5]  << 8) | resp_soil[6])  / 10.0
        data['ec']        = (resp_soil[7]   << 8) | resp_soil[8]
        data['ph']        = ((resp_soil[9]  << 8) | resp_soil[10]) / 10.0
        data['n']         = (resp_soil[11]  << 8) | resp_soil[12]
        data['p']         = (resp_soil[13]  << 8) | resp_soil[14]
        data['k']         = (resp_soil[15]  << 8) | resp_soil[16]

    if resp_solar and len(resp_solar) >= 5:
        data['solar'] = (resp_solar[3] << 8) | resp_solar[4]

    if resp_co2 and len(resp_co2) >= 5:
        data['co2'] = (resp_co2[3] << 8) | resp_co2[4]

    data['relay'] = relay.value()

    print(data)

    send_to_display(data)

    if nic:
        if http_post(data):
            print("HTTP POST: OK")
            fail_count = 0
        else:
            fail_count += 1
            print("HTTP POST: FAIL ({}/3)".format(fail_count))
            if fail_count >= 3:
                print("W5500 재초기화...")
                nic = init_network()
                fail_count = 0

    time.sleep_ms(LOOP_SLEEP_MS)
