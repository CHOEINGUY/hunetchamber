"""
tools_change_sensor_addr.py — 센서 Modbus 주소(slave addr) 변경 도구

사용법:
1. 센서 1개만 RS485 버스에 연결 (멀티드롭 X — 응답 충돌 방지)
2. main.py 대신 이 파일을 Thonny에서 실행
3. 콘솔에서 안내 따라 새 주소 입력

⚠ 센서마다 "주소 변경 레지스터" 다름. 데이터시트 확인 필수.
   - 흔한 위치: 0x07D0 (2000), 0x0100, 0x0030
   - 흔한 fc: 0x06 (Write Single Register)
"""
from machine import Pin, UART
import time

# ===== sensors.py와 동일한 설정 =====
UART_ID = 1
UART_TX_PIN = 8
UART_RX_PIN = 9
UART_DE_RE_PIN = 10
UART_BAUDRATE = 9600

uart = UART(UART_ID, baudrate=UART_BAUDRATE,
            tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN), timeout=100)
de_re = Pin(UART_DE_RE_PIN, Pin.OUT, value=0)


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


def rs485_query(req, wait_ms=300):
    while uart.any():
        uart.read()
    de_re.value(1)
    time.sleep_us(100)
    uart.write(req)
    time.sleep_ms(3 + len(req))
    de_re.value(0)
    time.sleep_ms(wait_ms)
    return uart.read() if uart.any() else None


def make_read(addr, reg, count, fc=0x03):
    req = bytes([addr, fc, (reg >> 8) & 0xFF, reg & 0xFF,
                 (count >> 8) & 0xFF, count & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def make_write_single(addr, reg, value, fc=0x06):
    """Write Single Register (fc=0x06)"""
    req = bytes([addr, fc, (reg >> 8) & 0xFF, reg & 0xFF,
                 (value >> 8) & 0xFF, value & 0xFF])
    crc = crc16(req)
    return req + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def scan_addr():
    """현재 버스에 어떤 addr 센서가 있는지 스캔 (1~10번 시도)."""
    print("=== addr 스캔 (1~10번) ===")
    found = []
    for a in range(1, 11):
        # 데이터 1개 읽기 시도
        req = make_read(a, 0x0000, 1)
        resp = rs485_query(req, wait_ms=200)
        if resp and len(resp) >= 5 and resp[0] == a:
            print(f"  addr {a}: ✓ 발견 (응답 {len(resp)} bytes)")
            found.append(a)
        else:
            print(f"  addr {a}: ─")
    return found


def change_addr(current_addr, new_addr, register=0x07D0):
    """addr 변경. register는 센서 데이터시트에 명시된 주소.
    기본값 0x07D0 = 흔한 값. 안 되면 0x0100, 0x0030 등 시도."""
    print(f"\n=== addr {current_addr} → {new_addr} (레지스터 0x{register:04X}) ===")
    req = make_write_single(current_addr, register, new_addr)
    resp = rs485_query(req, wait_ms=500)
    if resp:
        print(f"  응답: {bytes(resp).hex()}")
        if len(resp) >= 8 and resp[0] == current_addr:
            print(f"  ✓ 성공 가능성 높음. 재부팅 후 새 addr {new_addr}로 확인하세요.")
            return True
    print(f"  ✗ 응답 없음 또는 실패. 레지스터 주소 다를 수 있음.")
    return False


def verify_new_addr(new_addr):
    """변경된 addr로 읽기 시도."""
    print(f"\n=== 새 addr {new_addr} 검증 ===")
    print("  센서 전원 사이클(off→on) 한 번 해주세요 (필요한 경우만)...")
    time.sleep(2)
    req = make_read(new_addr, 0x0000, 1)
    resp = rs485_query(req)
    if resp and len(resp) >= 5 and resp[0] == new_addr:
        print(f"  ✓ addr {new_addr}로 응답 옴!")
        return True
    print(f"  ✗ 응답 없음. 레지스터 주소 데이터시트 다시 확인.")
    return False


# ===== 메인 인터랙티브 흐름 =====
print("=" * 50)
print("Modbus 센서 addr 변경 도구")
print("=" * 50)
print("\n⚠ 한 번에 센서 1개만 RS485 버스에 연결하세요.")
print("⚠ 데이터시트의 '주소 변경 레지스터' 확인하세요.")
print()

# 1) 현재 버스 스캔
found = scan_addr()
if not found:
    print("\n✗ 발견된 센서 없음. 결선/전원 확인 후 다시 실행.")
else:
    print(f"\n발견된 센서: addr {found}")

print("\n--- 사용 예시 (Thonny REPL에서 직접 호출) ---")
print(">>> change_addr(1, 2)              # 흔한 레지스터(0x07D0) 시도")
print(">>> change_addr(1, 2, 0x0100)      # 다른 레지스터")
print(">>> change_addr(1, 2, 0x0030)      # 또 다른 흔한 위치")
print(">>> verify_new_addr(2)             # 변경 후 검증")
print(">>> scan_addr()                    # 다시 스캔")
