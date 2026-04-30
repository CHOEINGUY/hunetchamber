from machine import UART, Pin, SoftSPI
import json
import time
import wiznet5k
import wiznet5k_socket as socket

# ── 핀 설정 ──────────────────────────────────────────
led   = Pin(25, Pin.OUT)
relay = Pin(2, Pin.OUT, value=1)  # active-low relay: 1=OFF, 0=ON
relay_state = 0
sensor_dir = Pin(6, Pin.OUT, value=0)  # sensor RS485 DE+RE: 1=TX, 0=RX
uart  = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=600)

def set_relay(cmd):
    global relay_state
    relay_state = cmd & 0x01
    relay.value(0 if relay_state else 1)

# ── RP2350 디스플레이 UART ────────────────────────────
# Final wiring uses an extra TTL-to-RS485 module:
# Pico GP4(TX) -> TTL-RS485 DI, TTL-RS485 A/B -> RP2350 RS485 A/B
# Pico GP5(RX) <- TTL-RS485 RO
display_uart = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5), timeout=20)

def check_display_command():
    try:
        # '?' is a short poll request for the relay command
        display_uart.write(b'?')
        time.sleep_ms(10)
        if display_uart.any():
            cmd = display_uart.read(1)
            if cmd:
                set_relay(cmd[0])
                return True
    except Exception as e:
        print("Display Poll 오류:", e)
    return False

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
        relay_state,
    )
    try:
        while display_uart.any():
            display_uart.read()
        display_uart.write(msg.encode())
        time.sleep_ms(20)
        if display_uart.any():
            cmd = display_uart.read(1)
            if cmd:
                set_relay(cmd[0])
    except Exception as e:
        print("Display UART 오류:", e)

# ── W5500 SPI 설정 ───────────────────────────────────
# GP16(MISO) GP17(CS) GP18(SCK) GP19(MOSI) GP20(RST)
spi = SoftSPI(baudrate=100_000, polarity=1, phase=1,
              sck=Pin(18), mosi=Pin(19), miso=Pin(16))
cs  = Pin(17, Pin.OUT)
rst = Pin(20, Pin.OUT)

SERVER_IP   = '192.168.100.30'
SERVER_PORT = 8080
SERVER_PATH = '/sensor'
HTTP_TIMEOUT_SECONDS = 2
LOOP_SLEEP_MS = 500

def init_network():
    rst.value(0)
    time.sleep(0.5)
    rst.value(1)
    time.sleep(1)

    print("W5500 초기화...")
    nic = wiznet5k.WIZNET5K(spi, cs, reset=None, is_dhcp=True)
    socket.set_interface(nic)

    for i in range(20):
        phycfgr = nic.read(0x002E, 0x00)[0]
        lnk = phycfgr & 0x01
        print("  {}초: PHYCFGR=0x{:02X} LNK={}".format(i + 1, phycfgr, lnk))
        if lnk:
            break
        time.sleep(1)

    # 일부 MicroPython wiznet 포트에서 link_status가 불안정해서 직접 확인한 링크를 신뢰한다.
    wiznet5k.WIZNET5K.link_status = property(lambda self: 1)
    print("DHCP 설정 완료:", nic.ifconfig)
    return nic

def http_post(data):
    body = json.dumps(data)
    request = (
        "POST {} HTTP/1.1\r\n"
        "Host: {}\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n"
        "\r\n"
        "{}"
    ).format(SERVER_PATH, SERVER_IP, len(body), body)

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
    sensor_dir.value(0)
    while uart.any():
        uart.read()
        time.sleep_ms(10)
    sensor_dir.value(1)
    time.sleep_us(100)
    uart.write(req)
    try:
        uart.flush()
    except AttributeError:
        time.sleep_ms(10)
    sensor_dir.value(0)
    time.sleep_ms(wait_ms)
    return uart.read() if uart.any() else None

# ── 센서 요청 패킷 ────────────────────────────────────
REQ_TH    = make_read(0x01, 0x0000, 2)
REQ_SOIL  = make_read(0x02, 0x0000, 7)
REQ_SOLAR = make_read(0x03, 0x0000, 1)
REQ_CO2   = make_read(0x04, 0x0000, 1, fc=0x04)

# ── 메인 ─────────────────────────────────────────────
print("=== Hunet 통합 센서 시작 (Pico) ===")
try:
    nic = init_network()
except Exception as e:
    print("W5500 초기화 실패, 네트워크 비활성화:", e)
    nic = None
fail_count = 0

while True:
    led.toggle()

    check_display_command()
    resp_th    = read_sensor(REQ_TH, 250)
    
    check_display_command()
    time.sleep_ms(50)
    resp_soil  = read_sensor(REQ_SOIL, 350)
    
    check_display_command()
    time.sleep_ms(50)
    resp_solar = read_sensor(REQ_SOLAR, 250)
    
    check_display_command()
    time.sleep_ms(50)
    resp_co2   = read_sensor(REQ_CO2, 450)
    
    check_display_command()

    data = {}

    if resp_th and len(resp_th) >= 9:
        data['humidity'] = ((resp_th[3] << 8) | resp_th[4]) / 10.0
        data['air_temp'] = ((resp_th[5] << 8) | resp_th[6]) / 10.0

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

    print(data)
    send_to_display(data)  # 전송 후 릴레이 명령도 수신

    if nic:
        if http_post(data):
            print("HTTP POST: OK")
            fail_count = 0
        else:
            fail_count += 1
            print("HTTP POST: FAIL ({}/3)".format(fail_count))
            if fail_count >= 3:
                print("W5500 재초기화...")
                try:
                    nic = init_network()
                except Exception as e:
                    print("W5500 재초기화 실패:", e)
                    nic = None
                fail_count = 0

    time.sleep_ms(LOOP_SLEEP_MS)
