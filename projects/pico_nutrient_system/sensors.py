"""
sensors.py — RS485 Modbus RTU 센서 폴링 모듈
하드웨어:
  - UART1 (GP8 TX / GP9 RX)
  - MAX485 트랜시버 DE+RE 묶음 → GP10 (HIGH=송신, LOW=수신)
  - 종단저항 120Ω: MAX485쪽 + 마지막 센서쪽

기반 코드: hunetchamber/projects/farm_sensor_gateway/firmware/pico/main.py
원본은 UART0 (GP0/1) + DE/RE GP6 사용 → 우리는 UART1 + GP10 사용
(GP0/1은 디스플레이 RS485 대안용으로 비워둠)
"""
from machine import Pin, UART
import time

# ===== RS485 핀 설정 =====
UART_ID         = 1
UART_TX_PIN     = 8
UART_RX_PIN     = 9
UART_DE_RE_PIN  = 10
UART_BAUDRATE   = 9600

uart = UART(UART_ID, baudrate=UART_BAUDRATE,
            tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN), timeout=600)
de_re = Pin(UART_DE_RE_PIN, Pin.OUT, value=0)  # LOW=수신


# ===== 센서 정의 (저분 farm_sensor_gateway 매핑 기준) =====
# Slave ID 0x01~0x04. 출고 기본은 모두 0x01이라 멀티드롭 전 별도 변경 필요.
SENSORS_ENABLED = {
    "th":    True,    # 0x01 온습도 (air temp + humidity)
    "soil":  True,    # 0x02 토양 5-in-1 (수분/온도/EC/pH/N/P/K)
    "solar": False,   # 0x03 조도 (보유 안 함)
    "co2":   False,   # 0x04 CO2 (보유 안 함)
    # 추가 예정 (양액 측정):
    "sol_ec": False,  # 0x05 양액 EC (구매 후 활성화, addr/reg 미정)
    "sol_ph": False,  # 0x06 양액 pH (구매 후 활성화, addr/reg 미정)
}


# ===== 폴링 데이터 캐시 =====
data = {
    # 온습도 (0x01)
    "air_temp":  None,    # °C
    "humidity":  None,    # %
    # 토양 5-in-1 (0x02)
    "moisture":  None,    # % (토양수분)
    "soil_temp": None,    # °C
    "soil_ec":   None,    # μS/cm (토양 EC, 정수)
    "soil_ph":   None,    # pH (0~14)
    "n":         None,    # mg/kg (질소)
    "p":         None,    # mg/kg (인)
    "k":         None,    # mg/kg (칼륨)
    # 조도 (0x03)
    "solar":     None,    # W/m²
    # CO2 (0x04)
    "co2":       None,    # ppm
    # 양액 측정 (별도 센서)
    "sol_ec":    None,
    "sol_ph":    None,
    # 메타
    "last_ok_ms": {},
    "err_count":  {},
}


# ===== Modbus 유틸 (저분 코드 그대로) =====
def crc16(buf):
    crc = 0xFFFF
    for byte in buf:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def make_read(addr, reg, count, fc=0x03):
    """Modbus Read 프레임. fc=0x03 (Holding Reg) 또는 0x04 (Input Reg, CO2용)."""
    req = bytes([addr, fc, (reg >> 8) & 0xFF, reg & 0xFF,
                 (count >> 8) & 0xFF, count & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def rs485_query(req, wait_ms=300):
    """송신 → 응답 대기 → 수신 (저분 read_sensor 로직 그대로)."""
    de_re.value(0)            # 수신 모드 초기
    while uart.any():
        uart.read()
        time.sleep_ms(10)
    de_re.value(1)            # 송신 모드
    time.sleep_us(100)
    uart.write(req)
    try:
        uart.flush()
    except AttributeError:
        time.sleep_ms(10)
    de_re.value(0)            # 수신 모드 복귀
    time.sleep_ms(wait_ms)
    return uart.read() if uart.any() else None


def _bump_err(key):
    data["err_count"][key] = data["err_count"].get(key, 0) + 1


# ===== 센서별 요청 패킷 (사전 계산) =====
REQ_TH    = make_read(0x01, 0x0000, 2)        # 온습도 2 레지스터
REQ_SOIL  = make_read(0x02, 0x0000, 7)        # 토양 5-in-1: 7 레지스터
REQ_SOLAR = make_read(0x03, 0x0000, 1)        # 조도 1 레지스터
REQ_CO2   = make_read(0x04, 0x0000, 1, fc=0x04)  # CO2 1 레지스터 (fc=0x04!)


# ===== 센서별 폴링 =====
def read_temp_humidity():
    """addr 0x01: 습도(reg 0) /10, 온도(reg 1) /10. signed temp."""
    resp = rs485_query(REQ_TH, wait_ms=250)
    if not resp or len(resp) < 9:
        _bump_err("th")
        return None
    if resp[0] != 0x01 or resp[1] != 0x03:
        _bump_err("th")
        return None
    body = resp[:-2]
    got_crc = resp[-2] | (resp[-1] << 8)
    if crc16(body) != got_crc:
        _bump_err("th")
        return None
    humidity = ((resp[3] << 8) | resp[4]) / 10.0
    raw_temp = (resp[5] << 8) | resp[6]
    if raw_temp & 0x8000:
        raw_temp -= 0x10000
    air_temp = raw_temp / 10.0
    if not (-40 <= air_temp <= 80) or not (0 <= humidity <= 100):
        _bump_err("th")
        return None
    data["humidity"] = humidity
    data["air_temp"] = air_temp
    data["last_ok_ms"]["th"] = time.ticks_ms()
    return air_temp, humidity


def read_soil_5in1():
    """addr 0x02: 7 레지스터 = 수분/토양온도/EC/pH/N/P/K.
       (저분 farm_main.py 파싱 그대로)"""
    resp = rs485_query(REQ_SOIL, wait_ms=350)
    if not resp or len(resp) < 17:
        _bump_err("soil")
        return None
    if resp[0] != 0x02 or resp[1] != 0x03:
        _bump_err("soil")
        return None
    body = resp[:-2]
    got_crc = resp[-2] | (resp[-1] << 8)
    if crc16(body) != got_crc:
        _bump_err("soil")
        return None
    moisture  = ((resp[3]  << 8) | resp[4])  / 10.0
    raw_st    = (resp[5]   << 8) | resp[6]
    if raw_st & 0x8000:
        raw_st -= 0x10000
    soil_temp = raw_st / 10.0
    soil_ec   = (resp[7]   << 8) | resp[8]      # μS/cm 정수
    soil_ph   = ((resp[9]  << 8) | resp[10]) / 10.0
    n_val     = (resp[11]  << 8) | resp[12]
    p_val     = (resp[13]  << 8) | resp[14]
    k_val     = (resp[15]  << 8) | resp[16]
    data["moisture"]  = moisture
    data["soil_temp"] = soil_temp
    data["soil_ec"]   = soil_ec
    data["soil_ph"]   = soil_ph
    data["n"]         = n_val
    data["p"]         = p_val
    data["k"]         = k_val
    data["last_ok_ms"]["soil"] = time.ticks_ms()
    return moisture, soil_temp, soil_ec, soil_ph


def read_solar():
    """addr 0x03: 일사량 W/m² 1 레지스터."""
    resp = rs485_query(REQ_SOLAR, wait_ms=250)
    if not resp or len(resp) < 7:
        _bump_err("solar")
        return None
    body = resp[:-2]
    if crc16(body) != (resp[-2] | (resp[-1] << 8)):
        _bump_err("solar")
        return None
    val = (resp[3] << 8) | resp[4]
    data["solar"] = val
    data["last_ok_ms"]["solar"] = time.ticks_ms()
    return val


def read_co2():
    """addr 0x04: CO2 ppm, fc=0x04 (Input Reg)."""
    resp = rs485_query(REQ_CO2, wait_ms=450)
    if not resp or len(resp) < 7:
        _bump_err("co2")
        return None
    if resp[0] != 0x04 or resp[1] != 0x04:
        _bump_err("co2")
        return None
    body = resp[:-2]
    if crc16(body) != (resp[-2] | (resp[-1] << 8)):
        _bump_err("co2")
        return None
    val = (resp[3] << 8) | resp[4]
    data["co2"] = val
    data["last_ok_ms"]["co2"] = time.ticks_ms()
    return val


# ===== 전체 폴링 =====
def poll_all():
    """모든 활성 센서 순차 폴링. 1회 ~약 1.5초 (모두 enabled 시)."""
    if SENSORS_ENABLED.get("th"):
        try: read_temp_humidity()
        except Exception as e: print("th err:", e); _bump_err("th")
        time.sleep_ms(50)

    if SENSORS_ENABLED.get("soil"):
        try: read_soil_5in1()
        except Exception as e: print("soil err:", e); _bump_err("soil")
        time.sleep_ms(50)

    if SENSORS_ENABLED.get("solar"):
        try: read_solar()
        except Exception as e: print("solar err:", e); _bump_err("solar")
        time.sleep_ms(50)

    if SENSORS_ENABLED.get("co2"):
        try: read_co2()
        except Exception as e: print("co2 err:", e); _bump_err("co2")
        time.sleep_ms(50)

    # 양액 EC/pH는 별도 센서 도착 후 활성화


def age_seconds(key):
    ms = data["last_ok_ms"].get(key)
    if ms is None:
        return -1
    return time.ticks_diff(time.ticks_ms(), ms) // 1000


def is_stale(key, threshold_s=15):
    age = age_seconds(key)
    return age < 0 or age > threshold_s
