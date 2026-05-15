"""
display_rs485.py — Pico W ↔ RP2350 디스플레이 RS485 통신 모듈
                   (W5500 이더넷 대안)

하드웨어:
  - UART0 (GP0 TX / GP1 RX)
  - MAX485 #2 트랜시버 DE+RE 묶음 → GP20 (HIGH=송신, LOW=수신)
  - baudrate 115200 (저분 fridge_controller 코드 기준)
  - 종단저항 120Ω: MAX485 측 + 디스플레이 측 각각

프로토콜: 텍스트 줄 기반 (저분 코드 패턴 그대로)
  Pico → 디스플레이: "STATUS busy=0 ec=1.20 humidity=65.0 temp_c=23.5 led=50 fan=30 ..."
  디스플레이 → Pico: 명령어 (예: "mix", "led 80", "fan 30", "stop")

⚠ 이 파일은 W5500 이더넷이 안 될 경우 폴백용으로 준비. main.py에서 import 안 함.
   사용하려면 main.py에서 import display_rs485 + 폴링 스레드 + 명령 핸들러 등록.
"""
from machine import Pin, UART
import time

# ===== RS485 핀 설정 (디스플레이용, 센서와 별개) =====
UART_ID         = 0
UART_TX_PIN     = 0
UART_RX_PIN     = 1
UART_DE_RE_PIN  = 20
UART_BAUDRATE   = 115200    # 저분 코드 기준
LINE_TIMEOUT_MS = 20

uart = UART(UART_ID, baudrate=UART_BAUDRATE,
            tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN), timeout=LINE_TIMEOUT_MS)
de_re = Pin(UART_DE_RE_PIN, Pin.OUT, value=0)  # LOW=수신


# ===== 송신 (Pico → 디스플레이) =====
def send_line(line):
    """디스플레이로 한 줄 송신. DE/RE 자동 토글."""
    de_re.value(1)            # 송신 모드
    time.sleep_ms(2)
    uart.write((line + "\n").encode())
    try:
        uart.flush()          # 송신 완료 대기
    except AttributeError:
        time.sleep_ms(2 + len(line) // 10)  # MicroPython 버전별 fallback
    time.sleep_ms(2)
    de_re.value(0)            # 수신 모드 복귀


def make_status_line(state_dict):
    """state_dict → JSON 문자열 (한 줄). 디스플레이는 prefix 'STATUS ' 제거 후 json.loads()."""
    import json as _json
    return "STATUS " + _json.dumps(state_dict)


# ===== 수신 (디스플레이 → Pico) =====
def check_commands(handler):
    """수신 버퍼 확인. 명령 발견 시 handler(cmd_text)에 위임.
    handler는 main.py가 등록 (예: pump_on, start_mix 등 호출하는 함수)."""
    de_re.value(0)            # 수신 모드 보장
    while uart.any():
        try:
            line = uart.readline()
        except AttributeError:
            line = uart.read()
        if not line:
            return
        try:
            text = line.decode().strip()
        except Exception:
            continue
        if text:
            print("DISP CMD:", text)
            try:
                handler(text)
            except Exception as e:
                print("DISP handler err:", e)


# ===== 주기적 STATUS 송신 (main.py 루프에서 호출) =====
_last_status_ms = 0
STATUS_INTERVAL_MS = 1000

def maybe_send_status(state_dict):
    """main.py가 매 루프에서 호출. 1초 마다 STATUS 라인 송신."""
    global _last_status_ms
    if time.ticks_diff(time.ticks_ms(), _last_status_ms) < STATUS_INTERVAL_MS:
        return
    _last_status_ms = time.ticks_ms()
    send_line(make_status_line(state_dict))


# ===== main.py 통합 예시 (이 파일 활성화 시) =====
"""
# main.py에 추가할 코드:

import display_rs485

def _display_cmd_handler(cmd_text):
    \"\"\"디스플레이가 보낸 명령 처리\"\"\"
    parts = cmd_text.lower().split()
    if not parts: return
    c = parts[0]
    if c == "mix":
        start_mix()
    elif c == "stop":
        abort_mix()
    elif c == "led" and len(parts) == 2:
        led_set(int(parts[1]))
    elif c == "fan" and len(parts) == 2:
        fan_set(int(parts[1]))
    elif c == "pump" and len(parts) == 3:
        idx = int(parts[1]); s = float(parts[2])
        if 0 <= idx < 4:
            pump_run_async(idx, s)
    # ... 등등

def _display_thread():
    while True:
        try:
            display_rs485.check_commands(_display_cmd_handler)
            display_rs485.maybe_send_status({
                "busy": int(busy),
                "ec": (sensors.data.get("ec") if SENSORS_AVAILABLE else None),
                "humidity": (sensors.data.get("humidity") if SENSORS_AVAILABLE else None),
                "temp_c": (sensors.data.get("temp_c") if SENSORS_AVAILABLE else None),
                "soil": (sensors.data.get("soil_moisture") if SENSORS_AVAILABLE else None),
                "led": led_duty_pct,
                "fan": fan_duty_pct,
                "stir": stirrer_state,
                "pump1": state[0], "pump2": state[1],
                "pump3": state[2], "pump4": state[3],
            })
        except Exception as e:
            print("disp thread err:", e)
        time.sleep_ms(50)

# main 진입점에 추가:
_thread.start_new_thread(_display_thread, ())
"""
