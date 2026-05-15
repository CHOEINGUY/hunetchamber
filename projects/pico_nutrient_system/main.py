"""
Pico W - 양액 자동 조제 시스템
- CH1 급수 (KPHM100) / CH2 양액A / CH3 양액B / CH4 출수 (다이어프램)
- mL 단위 정량 토출
- '혼합 시작' 자동 시퀀스: 급수 → A+B 동시 → 완료
- 출수 정량/수동
- 펌프별 유량 보정 (실측 → 자동 계산 → 플래시 저장)
- 레시피 값 플래시 저장
"""
import network
import socket
import time
import gc
import machine
from machine import Pin, PWM
import _thread
import json

# RS485 센서 모듈 (별도 파일)
try:
    import sensors
    SENSORS_AVAILABLE = True
except ImportError:
    sensors = None
    SENSORS_AVAILABLE = False
    print("WARN: sensors.py 없음 — 센서 기능 비활성")

# RS485 디스플레이 모듈 (W5500 이더넷 안 쓰는 경우)
try:
    import display_rs485
    DISPLAY_RS485_AVAILABLE = True
except ImportError:
    display_rs485 = None
    DISPLAY_RS485_AVAILABLE = False
    print("WARN: display_rs485.py 없음 — 디스플레이 RS485 통신 비활성")

SENSOR_POLL_INTERVAL_S = 5   # 5초마다 전체 센서 폴링


# ===== 고정 설정 =====
SSID = "hunet_sens"
PASSWORD = "gaia00975"

PUMP_PINS   = [15, 14, 13, 12]
PUMP_LABELS = ["급수", "양액 A", "양액 B", "출수"]
PUMP_MODELS = ["KPHM100-HB", "NKP-DC-B06B", "NKP-DC-B06B", "티앤디 다이어프램"]

# 2번 MOSFET 모듈 (SZH-AT021 IRF540N 4ch)
STIRRER_PIN = 11   # CH1: 교반기 ON/OFF
LED_PIN     = 16   # CH2: LED 스트립 PWM 디밍
FAN_PIN     = 18   # CH3: 팬 PWM 속도제어
# CH4 예비

# PWM 설정 — SZH-AT021 포토커플러(PC817) 한계로 1~2kHz 권장
PWM_FREQ = 1000              # 펌프/LED/팬 공통 1kHz
NUTRIENT_PWM_DUTY = 33       # 양액 펌프 PWM 듀티(%): 33% → ~30mL/min → 2mL 4초, ±2.5%

MAX_RUN_SECONDS = 600
# 채널별 보정 기본 시간(초). 측정량이 너무 적으면 정확도 떨어져서
# 토출량 작은 펌프(CH2/3)는 더 길게 잡음. 사용자가 UI에서 변경 가능.
DEFAULT_CALIB_SEC = [30, 60, 60, 10]
# 실측 보정값 (2026-05-14): CH1=100mL/min, CH2/3=90mL/min 풀속도. CH4 미측정.
DEFAULT_FLOW = [100/60, 90/60, 90/60, 5.00]   # mL/sec (= 1.667, 1.500, 1.500, 5.00)
# 전호 R&D 레시피: 1L 급수당 A/B 각 2mL (500배 희석, EC ~1.2)
DEFAULT_RECIPE = {"water": 1000.0, "A": 2.0, "B": 2.0, "stir": 30.0}

CALIB_FILE = "calibration.json"
RECIPE_FILE = "recipe.json"


# ===== 핀/상태 =====
# ⚡ 부팅 시 액추에이터 자동 ON 방지: 모든 출력 핀을 명시적으로 LOW로 먼저 잡음
# (PWM 객체 생성 전 GPIO를 LOW로 잡지 않으면 floating 상태 → MOSFET 모듈이 ON 인식)
for _p in PUMP_PINS:
    Pin(_p, Pin.OUT, value=0)
Pin(STIRRER_PIN, Pin.OUT, value=0)
Pin(LED_PIN, Pin.OUT, value=0)
Pin(FAN_PIN, Pin.OUT, value=0)

# 그 다음 PWM 객체로 전환 (이미 LOW 상태였으니 글리치 최소화)
pumps = []
for _p in PUMP_PINS:
    _pwm = PWM(Pin(_p))
    _pwm.duty_u16(0)     # ← 주파수 설정 전에 먼저 0%로
    _pwm.freq(PWM_FREQ)
    _pwm.duty_u16(0)     # ← 주파수 변경 후 다시 0% 확실하게
    pumps.append(_pwm)
state = [0, 0, 0, 0]
timers = [None, None, None, None]
onboard_led = machine.Pin("LED", machine.Pin.OUT, value=0)

stirrer = machine.Pin(STIRRER_PIN, machine.Pin.OUT, value=0)
stirrer_state = 0
stirrer_timer = None

# LED 스트립 (GP16, PWM 디밍) / 팬 (GP18, PWM 속도제어)
led_pwm = PWM(Pin(LED_PIN));  led_pwm.duty_u16(0);  led_pwm.freq(PWM_FREQ);  led_pwm.duty_u16(0)
fan_pwm = PWM(Pin(FAN_PIN));  fan_pwm.duty_u16(0);  fan_pwm.freq(PWM_FREQ);  fan_pwm.duty_u16(0)
led_duty_pct = 0
fan_duty_pct = 0

flow   = list(DEFAULT_FLOW)
recipe = dict(DEFAULT_RECIPE)
# 각 채널에 대해 마지막으로 실행한 보정 시간(초). 보정 적용 시 이 값으로 ml/sec 계산.
last_calib_sec = list(DEFAULT_CALIB_SEC)
# 수동 측정 시작 시각(ms). 0 = 측정 중 아님.
cal_start_ms = [0, 0, 0, 0]

busy = False
status_text = "대기"
seq_lock = _thread.allocate_lock()

seq_abort = False
step_start_ms = 0
step_duration_s = 0.0


def _set_step(text, duration_s=0.0):
    global status_text, step_start_ms, step_duration_s
    status_text = text
    step_start_ms = time.ticks_ms()
    step_duration_s = max(0.0, float(duration_s))


def _display_payload():
    """디스플레이로 보낼 현재 상태 페이로드 (JSON 직렬화 가능)."""
    payload = {
        "busy": int(busy),
        "step": status_text,
        "p1": state[0], "p2": state[1], "p3": state[2], "p4": state[3],
        "stir": stirrer_state,
        "led": led_duty_pct,
        "fan": fan_duty_pct,
        "recipe": recipe,
    }
    if SENSORS_AVAILABLE:
        sd = sensors.data
        payload["air_t"]   = sd.get("air_temp")
        payload["humid"]   = sd.get("humidity")
        payload["moist"]   = sd.get("moisture")
        payload["soil_t"]  = sd.get("soil_temp")
        payload["soil_ec"] = sd.get("soil_ec")
        payload["soil_ph"] = sd.get("soil_ph")
        payload["n"]       = sd.get("n")
        payload["p"]       = sd.get("p")
        payload["k"]       = sd.get("k")
    return payload


def _yield_display():
    """블로킹 루프 안에서 호출. 디스플레이 RS485 통신 유지 (시퀀스 중 STATUS 끊김 방지).
    예외 발생해도 시퀀스/펌프 동작 막지 않음."""
    if DISPLAY_RS485_AVAILABLE:
        try:
            display_rs485.check_commands(_display_cmd_handler)
            display_rs485.maybe_send_status(_display_payload())
        except Exception:
            pass


# ===== JSON 영속화 =====
def _save_json(path, obj):
    try:
        with open(path, "w") as f:
            json.dump(obj, f)
    except Exception as e:
        print("save err", path, e)


def _load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def load_persisted():
    global flow, recipe
    c = _load_json(CALIB_FILE, None)
    if isinstance(c, list) and len(c) == 4:
        try:
            flow = [max(0.001, float(x)) for x in c]
        except Exception:
            pass
    r = _load_json(RECIPE_FILE, None)
    if isinstance(r, dict):
        for k in ("water", "A", "B", "stir"):
            if k in r:
                try:
                    recipe[k] = max(0.0, float(r[k]))
                except Exception:
                    pass


# ===== 펌프/교반기 제어 =====
def _update_led():
    onboard_led.value(1 if (any(state) or stirrer_state) else 0)


def stirrer_on():
    global stirrer_state
    stirrer.value(1)
    stirrer_state = 1
    _update_led()


def _stirrer_off_isr():
    global stirrer_state
    stirrer.value(0)
    stirrer_state = 0


def stirrer_off():
    global stirrer_timer
    _stirrer_off_isr()
    _update_led()
    if stirrer_timer:
        try: stirrer_timer.deinit()
        except Exception: pass
        stirrer_timer = None


def stirrer_run_async(seconds):
    global stirrer_timer
    seconds = max(0.05, min(seconds, MAX_RUN_SECONDS))
    stirrer_on()
    if stirrer_timer:
        try: stirrer_timer.deinit()
        except Exception: pass
    t = machine.Timer()
    t.init(period=int(seconds * 1000),
           mode=machine.Timer.ONE_SHOT,
           callback=lambda _t: _stirrer_off_isr())
    stirrer_timer = t


def stirrer_run_blocking(seconds):
    seconds = max(0.05, min(seconds, MAX_RUN_SECONDS))
    stirrer_on()
    deadline = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if stirrer_state == 0:
            return
        _yield_display()
        time.sleep_ms(50)
    stirrer_off()


def pump_on(idx):
    """풀듀티 ON (PWM 100%)."""
    pumps[idx].duty_u16(65535)
    state[idx] = 1
    _update_led()


def pump_on_pwm(idx, duty_pct):
    """PWM 듀티 지정 ON. 양액 펌프 정밀 도징용.
    저듀티(50% 미만)에서 정지→시동 시 stall 방지를 위해 100ms 풀파워 킥."""
    duty_pct = max(0, min(100, duty_pct))
    # Start kick: 정지에서 저듀티 시동 시
    if state[idx] == 0 and 0 < duty_pct < 50:
        pumps[idx].duty_u16(65535)
        time.sleep_ms(100)
    pumps[idx].duty_u16(int(duty_pct / 100 * 65535))
    state[idx] = 1
    _update_led()


def _pump_off_isr(idx):
    """ISR 컨텍스트에서 호출 안전 - GPIO 만 만지고 LED/dispose 는 main 에서."""
    pumps[idx].duty_u16(0)
    state[idx] = 0


def pump_off(idx):
    _pump_off_isr(idx)
    _update_led()
    t = timers[idx]
    if t:
        try: t.deinit()
        except Exception: pass
        timers[idx] = None


def pump_run_async(idx, seconds):
    """Timer 기반 비동기 ON. 즉시 반환."""
    seconds = max(0.05, min(seconds, MAX_RUN_SECONDS))
    pump_on(idx)
    if timers[idx]:
        try: timers[idx].deinit()
        except Exception: pass
    t = machine.Timer()
    t.init(period=int(seconds * 1000),
           mode=machine.Timer.ONE_SHOT,
           callback=lambda _t, i=idx: _pump_off_isr(i))
    timers[idx] = t


def pump_run_blocking(idx, seconds):
    """sequence 안에서 사용. 끝까지 대기. 대기 중 디스플레이 통신 유지."""
    seconds = max(0.05, min(seconds, MAX_RUN_SECONDS))
    pump_on(idx)
    deadline = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if state[idx] == 0:
            return
        _yield_display()
        time.sleep_ms(50)
    pump_off(idx)


def pump_run_blocking_pwm(idx, seconds, duty_pct):
    """PWM 듀티 지정 + 끝까지 대기. 양액 펌프 정밀 도징용."""
    seconds = max(0.05, min(seconds, MAX_RUN_SECONDS))
    pump_on_pwm(idx, duty_pct)
    deadline = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if state[idx] == 0:
            return
        _yield_display()
        time.sleep_ms(50)
    pump_off(idx)


def pump_run_async_pwm(idx, seconds, duty_pct):
    """PWM 듀티 지정 + Timer 기반 비동기."""
    seconds = max(0.05, min(seconds, MAX_RUN_SECONDS))
    pump_on_pwm(idx, duty_pct)
    if timers[idx]:
        try: timers[idx].deinit()
        except Exception: pass
    t = machine.Timer()
    t.init(period=int(seconds * 1000),
           mode=machine.Timer.ONE_SHOT,
           callback=lambda _t, i=idx: _pump_off_isr(i))
    timers[idx] = t


def dose_async(idx, ml):
    if flow[idx] <= 0 or ml <= 0:
        return
    pump_run_async(idx, ml / flow[idx])


# ===== LED 스트립 / 팬 (2번 MOSFET CH2/CH3) =====
def led_set(duty_pct):
    """LED 듀티(%) 설정. 0=OFF, 100=풀."""
    global led_duty_pct
    duty_pct = max(0, min(100, int(duty_pct)))
    led_duty_pct = duty_pct
    led_pwm.duty_u16(int(duty_pct / 100 * 65535))


def fan_set(duty_pct):
    """팬 듀티(%) 설정. 0=OFF, 100=풀. 저듀티에서 stall 시 start kick 필요."""
    global fan_duty_pct
    duty_pct = max(0, min(100, int(duty_pct)))
    # start kick: 정지에서 저듀티 시동 시 100% 짧게 → 목표 듀티
    if fan_duty_pct == 0 and 0 < duty_pct < 50:
        fan_pwm.duty_u16(65535)
        time.sleep_ms(100)
    fan_duty_pct = duty_pct
    fan_pwm.duty_u16(int(duty_pct / 100 * 65535))


def all_off():
    for i in range(4):
        pump_off(i)
    stirrer_off()
    led_set(0)
    fan_set(0)


# ===== 통합 백그라운드 스레드 (센서 + 디스플레이 + 시퀀스) =====
# RP2040 MicroPython은 보조 스레드 1개만 안정적이라 모두 한 스레드에서 처리.
def _bg_thread():
    """모든 백그라운드 작업을 50ms 사이클로 처리:
       - 디스플레이 RS485 (명령 수신 + STATUS 송신)
       - 센서 폴링 (5초 주기)
       - 시퀀스 실행 (요청 시)
    """
    global busy, sequence_request
    last_sensor_ms = time.ticks_ms() - 100000   # 즉시 첫 폴링

    while True:
        try:
            # 1) 디스플레이 RS485 (매 사이클)
            if DISPLAY_RS485_AVAILABLE:
                try:
                    display_rs485.check_commands(_display_cmd_handler)
                    display_rs485.maybe_send_status(_display_payload())
                except Exception as e:
                    print("disp err:", e)

            # 2) 센서 폴링 (5초 주기, 시퀀스 중에는 폴링 안 함 — UART 충돌 X지만 우선순위 ↓)
            now = time.ticks_ms()
            if (SENSORS_AVAILABLE and not busy
                    and time.ticks_diff(now, last_sensor_ms) >= SENSOR_POLL_INTERVAL_S * 1000):
                try:
                    sensors.poll_all()
                except Exception as e:
                    print("sensor err:", e)
                last_sensor_ms = time.ticks_ms()

            # 3) 시퀀스 트리거
            if sequence_request and not busy:
                with seq_lock:
                    sequence_request = False
                    busy = True
                try:
                    _run_sequence()
                except Exception as e:
                    print("seq fatal:", e)
                    _set_step(f"치명 오류: {e}")
                    all_off()
                finally:
                    busy = False

        except Exception as e:
            print("bg thread err:", e)

        time.sleep_ms(50)


# ===== 디스플레이 RS485 명령 핸들러 =====
def _display_cmd_handler(cmd_text):
    """디스플레이가 RS485로 보낸 명령 처리.
    포맷 예: 'mix', 'stop', 'led 80', 'fan 30', 'stir on', 'pump 0 3.0', 'recipe 1000 2 2 30'"""
    parts = cmd_text.lower().split()
    if not parts:
        return
    c = parts[0]
    try:
        if c == "mix":
            start_mix()
        elif c == "stop":
            abort_mix()
        elif c == "led" and len(parts) == 2:
            led_set(int(parts[1]))
        elif c == "fan" and len(parts) == 2:
            fan_set(int(parts[1]))
        elif c == "stir" and len(parts) >= 2:
            if parts[1] == "on":
                stirrer_on()
            elif parts[1] == "off":
                stirrer_off()
            elif parts[1] == "run" and len(parts) == 3:
                stirrer_run_async(float(parts[2]))
        elif c == "pump" and len(parts) == 3:
            idx = int(parts[1])
            s = float(parts[2])
            if 0 <= idx < 4 and not busy:
                pump_run_async(idx, s)
        elif c == "recipe" and len(parts) == 5:
            update_recipe(water=float(parts[1]), a=float(parts[2]),
                          b=float(parts[3]), stir=float(parts[4]))
        else:
            print("disp: unknown cmd", cmd_text)
    except Exception as e:
        print("disp cmd parse err:", e)


# (옛 _display_thread / _sensor_thread / _seq_thread 는 _bg_thread로 통합됨)


# ===== 자동 시퀀스 =====
def _abortable_sleep(seconds):
    """seq_abort 가 켜지면 즉시 종료. 대기 중 디스플레이 통신 유지."""
    end = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        if seq_abort:
            return
        _yield_display()
        time.sleep_ms(50)


# 시퀀스 요청 플래그 (별 스레드 대신 백그라운드 스레드가 받아 실행)
sequence_request = False


def _run_sequence():
    """양액 자동 조제 시퀀스. _bg_thread에서 호출 (별 스레드 아님)."""
    global seq_abort
    try:
        # 1) 급수
        if seq_abort: return
        sec1 = recipe["water"] / flow[0]
        _set_step(f"급수 중 ({recipe['water']:.0f} mL)", sec1)
        pump_run_blocking(0, sec1)
        if seq_abort: return

        # 2) 수면 안정
        _set_step("수면 안정 (2초)", 2)
        _abortable_sleep(2)
        if seq_abort: return

        # 3) 양액 A + B 동시 (PWM 33% 정밀 도징, kick 보정 포함)
        duty = NUTRIENT_PWM_DUTY
        flow_a_pwm = flow[1] * duty / 100
        flow_b_pwm = flow[2] * duty / 100
        # Start kick 보정: 100ms 풀파워 = duty%에서 (100ms × 100/D) 와 동일 토출
        KICK_MS = 100
        kick_correction_s = (KICK_MS / 1000.0) * (100.0 / duty)   # duty=33 → ~0.303s
        sec_a = max(0.05, recipe["A"] / max(flow_a_pwm, 0.001) - kick_correction_s)
        sec_b = max(0.05, recipe["B"] / max(flow_b_pwm, 0.001) - kick_correction_s)
        _set_step(
            f"양액 A {recipe['A']:.2f}mL + B {recipe['B']:.2f}mL (PWM {duty}%)",
            max(sec_a, sec_b) + kick_correction_s,
        )
        pump_run_async_pwm(1, sec_a, duty)      # A 비동기 PWM (kick은 pump_on_pwm 안에서)
        pump_run_blocking_pwm(2, sec_b, duty)   # B 동기 PWM
        while state[1] and not seq_abort:
            _yield_display()
            time.sleep_ms(100)
        if seq_abort: return

        # 4) 교반
        stir_sec = recipe.get("stir", 0.0)
        if stir_sec > 0:
            _set_step(f"교반 중", stir_sec)
            stirrer_run_blocking(stir_sec)
            if seq_abort: return

        _set_step("혼합 완료", 3)
        _abortable_sleep(3)
        _set_step("대기")
    except Exception as e:
        _set_step(f"오류: {e}")
        all_off()
    finally:
        if seq_abort:
            _set_step("중단됨")


def start_mix():
    """시퀀스 시작 요청만 등록. 실제 실행은 _bg_thread가."""
    global busy, seq_abort, sequence_request
    with seq_lock:
        if busy or sequence_request:
            return False
        sequence_request = True
        seq_abort = False
    _set_step("시퀀스 시작 대기...", 0.5)
    return True


def abort_mix():
    """진행중 시퀀스 + 모든 출력 즉시 정지."""
    global seq_abort
    seq_abort = True
    all_off()


# ===== 보정 =====
def calibrate_run(idx, seconds):
    """N초 동작 (보정용). 사용한 시간을 기억해뒀다가 calibrate_apply 에서 사용."""
    if busy:
        return
    seconds = max(1.0, min(float(seconds), MAX_RUN_SECONDS))
    last_calib_sec[idx] = seconds
    pump_run_async(idx, seconds)


def calibrate_apply(idx, measured_ml):
    if measured_ml <= 0:
        return
    sec = last_calib_sec[idx]
    if sec <= 0:
        return
    flow[idx] = measured_ml / sec
    _save_json(CALIB_FILE, flow)


def calibrate_manual_start(idx):
    """수동 측정: 펌프 ON + 시작시각 기록. 사용자가 멈출 때까지 (안전장치 MAX_RUN_SECONDS)."""
    if busy:
        return
    cal_start_ms[idx] = time.ticks_ms()
    pump_run_async(idx, MAX_RUN_SECONDS)


def calibrate_manual_stop(idx):
    """수동 측정 종료: 펌프 OFF + 경과시간을 last_calib_sec 에 저장."""
    start = cal_start_ms[idx]
    pump_off(idx)
    if start == 0:
        return
    elapsed = time.ticks_diff(time.ticks_ms(), start) / 1000.0
    if elapsed > 0:
        last_calib_sec[idx] = elapsed
    cal_start_ms[idx] = 0


# ===== 레시피 저장 =====
def update_recipe(water=None, a=None, b=None, stir=None):
    if water is not None: recipe["water"] = max(0.0, float(water))
    if a     is not None: recipe["A"]     = max(0.0, float(a))
    if b     is not None: recipe["B"]     = max(0.0, float(b))
    if stir  is not None: recipe["stir"]  = max(0.0, float(stir))
    _save_json(RECIPE_FILE, recipe)


# ===== WiFi =====
def connect_wifi():
    """WiFi 연결 시도. 실패 시 None 반환 (오프라인 모드로 계속)."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print("WiFi 연결 중...", end="")
    for _ in range(30):
        if wlan.isconnected(): break
        print(".", end=""); time.sleep(1)
    print()
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print("연결됨! IP:", ip)
        return ip
    print("⚠ WiFi 실패 — 오프라인 모드 (HTTP 비활성, 펌프/센서/디스플레이는 정상)")
    return None


# ===== HTML =====
def _pump_status_dot(i):
    return "#22c55e" if state[i] else "#475569"


def _status_display():
    """status_text 에 남은시간 카운트다운 붙여서 반환."""
    if not busy or step_duration_s <= 0:
        return status_text
    elapsed = time.ticks_diff(time.ticks_ms(), step_start_ms) / 1000.0
    remaining = max(0.0, step_duration_s - elapsed)
    if remaining >= 60:
        mm = int(remaining // 60)
        ss = int(remaining % 60)
        return f"{status_text} · {mm}분 {ss}초 남음"
    return f"{status_text} · {int(remaining)}초 남음"


def render():
    _update_led()  # Timer ISR 가 LED 못 만져서 여기서 보정
    # 펌프/교반기/LED/팬 도는 동안 또는 측정 중에 자동 새로고침. / 로 리다이렉트 — 부수효과 URL 재실행 방지.
    any_measuring = any(t != 0 for t in cal_start_ms)
    any_running = any(state) or stirrer_state or led_duty_pct > 0 or fan_duty_pct > 0
    refresh = '<meta http-equiv="refresh" content="2;url=/">' if (busy or any_measuring or any_running) else ""

    # 자동 혼합 카드
    mix_btn = ("disabled" if busy else "")
    mix_card = f"""
    <div class="card">
      <h2>자동 혼합</h2>
      <div class="recipe-show">
        물 {recipe['water']:.0f} mL · A {recipe['A']:.2f} mL · B {recipe['B']:.2f} mL · 교반 {recipe['stir']:.0f}초
      </div>
      <a class="btn big {('off' if busy else 'on')}" href="/mix">▶ 혼합 시작</a>
      <details class="mt8">
        <summary>레시피 수정</summary>
        <form action="/recipe" method="get" class="row3">
          <label>물 (mL) <input name="water" value="{recipe['water']:.1f}" type="number" step="0.1" min="0"></label>
          <label>양액A (mL) <input name="a" value="{recipe['A']:.2f}" type="number" step="0.01" min="0"></label>
          <label>양액B (mL) <input name="b" value="{recipe['B']:.2f}" type="number" step="0.01" min="0"></label>
          <label>교반 (초) <input name="stir" value="{recipe['stir']:.0f}" type="number" step="1" min="0"></label>
          <button class="btn t">저장</button>
        </form>
      </details>
    </div>"""

    # 교반기 카드
    stir_state_text = "켜짐" if stirrer_state else "꺼짐"
    stir_dot = "#22c55e" if stirrer_state else "#475569"
    stir_card = f"""
    <div class="card">
      <h2>교반기</h2>
      <div class="row">
        <span class="dot" style="background:{stir_dot}"></span>
        <span>상태: {stir_state_text}</span>
      </div>
      <div class="btns mt8">
        <a class="btn on"  href="/stir/on">ON</a>
        <a class="btn off" href="/stir/off">OFF</a>
      </div>
      <form action="/stir/run" method="get" class="mt8">
        <label>N초 동작 <input name="s" type="number" step="1" min="1" value="30"> 초</label>
        <button class="btn t">시작</button>
      </form>
    </div>"""

    # 출수 카드 (CH4)
    drain_state = "켜짐" if state[3] else "꺼짐"
    drain_card = f"""
    <div class="card">
      <h2>출수 (다이어프램 CH4)</h2>
      <div class="row">
        <span class="dot" style="background:{_pump_status_dot(3)}"></span>
        <span>상태: {drain_state}</span>
      </div>
      <div class="btns mt8">
        <a class="btn on"  href="/pump/on?p=3">수동 ON</a>
        <a class="btn off" href="/pump/off?p=3">OFF</a>
      </div>
      <form action="/dose" method="get" class="mt8">
        <input type="hidden" name="p" value="3">
        <label>정량 출수 <input name="ml" type="number" step="1" min="1" value="500"> mL</label>
        <button class="btn t">시작</button>
      </form>
    </div>"""

    # 보정 카드
    calib_rows = ""
    for i in range(4):
        sec = last_calib_sec[i]
        measuring = cal_start_ms[i] != 0
        # 예상 토출량 — 현재 flow 기준 사용자가 받아야 할 대략적인 양
        expected_ml = flow[i] * sec
        running_badge = ' <span style="color:#fbbf24">● 측정 중</span>' if measuring else ''
        calib_rows += f"""
        <div class="calib-row">
          <div><strong>{PUMP_LABELS[i]}</strong> <span class="muted">{PUMP_MODELS[i]}</span>{running_badge}</div>
          <div class="muted">현재 유량: <b>{flow[i]:.3f}</b> mL/sec · 마지막 측정시간: <b>{sec:.1f}초</b></div>
          <div class="btns mt4">
            <a class="btn {'off' if measuring else 'on'} small" href="/{('calib_stop' if measuring else 'calib_start')}?p={i}">{'⏹ 측정 종료' if measuring else '▶ 측정 시작 (수동)'}</a>
          </div>
          <details class="mt4">
            <summary>고정시간 측정 / 보정 입력</summary>
            <form action="/calib_run" method="get" class="mt4">
              <input type="hidden" name="p" value="{i}">
              <label>시간 <input name="s" type="number" step="1" min="1" value="{sec:.0f}"> 초</label>
              <button class="btn t small">고정시간 측정 실행</button>
            </form>
            <form action="/calib_apply" method="get" class="mt4">
              <input type="hidden" name="p" value="{i}">
              <label>받은 양 <input name="ml" type="number" step="0.01" min="0" placeholder="mL (예: 180)"></label>
              <button class="btn t small">보정 적용</button>
            </form>
          </details>
        </div>"""
    calib_card = f"""
    <div class="card">
      <h2>유량 보정</h2>
      <p class="muted">① '측정 시작' → 펌프 켜짐. ② 종이컵(≈180mL) 꽉 차면 '측정 종료' → 경과시간 자동 저장. ③ '고정시간 측정 / 보정 입력' 펼쳐서 받은 양 입력 → '보정 적용'.</p>
      {calib_rows}
    </div>"""

    # 센서 카드 (RS485 Modbus RTU) — 저분 farm_sensor_gateway 매핑
    def _fmt(v, unit, fmt="{:.1f}"):
        return f"<b>{fmt.format(v)}</b> {unit}" if v is not None else f"<span class='muted'>N/A</span>"

    if SENSORS_AVAILABLE:
        sd = sensors.data
        sensor_card = f"""
        <div class="card">
          <h2>센서 (RS485)</h2>
          <h3 style="font-size:13px;color:#94a3b8;margin:6px 0 4px">🌡 공기 (addr 0x01)</h3>
          <div class="row3">
            <div>온도: {_fmt(sd['air_temp'], '°C')}</div>
            <div>습도: {_fmt(sd['humidity'], '%')}</div>
            <div class="muted">{sensors.age_seconds('th')}s 전</div>
          </div>

          <h3 style="font-size:13px;color:#94a3b8;margin:10px 0 4px">🪴 토양 5-in-1 (addr 0x02)</h3>
          <div class="row3">
            <div>수분: {_fmt(sd['moisture'], '%')}</div>
            <div>토양온도: {_fmt(sd['soil_temp'], '°C')}</div>
            <div>EC: {_fmt(sd['soil_ec'], 'μS/cm', '{:.0f}')}</div>
          </div>
          <div class="row3 mt4">
            <div>pH: {_fmt(sd['soil_ph'], '', '{:.1f}')}</div>
            <div>N: {_fmt(sd['n'], 'mg/kg', '{:.0f}')}</div>
            <div>P: {_fmt(sd['p'], 'mg/kg', '{:.0f}')}</div>
          </div>
          <div class="row3 mt4">
            <div>K: {_fmt(sd['k'], 'mg/kg', '{:.0f}')}</div>
            <div class="muted">{sensors.age_seconds('soil')}s 전</div>
          </div>

          <p class="muted mt8">
            5초 폴링 · 양액 EC/pH 센서 도착 후 추가 ·
            에러 카운트 {sd.get('err_count', {})}
          </p>
        </div>"""
    else:
        sensor_card = """
        <div class="card">
          <h2>센서</h2>
          <p class="muted">sensors.py 모듈 없음 — RS485 비활성</p>
        </div>"""

    # LED / 팬 카드 (2번 MOSFET CH2/CH3)
    led_dot = "#22c55e" if led_duty_pct > 0 else "#475569"
    fan_dot = "#22c55e" if fan_duty_pct > 0 else "#475569"
    led_fan_card = f"""
    <div class="card">
      <h2>LED 스트립 / 팬</h2>
      <div class="row">
        <span class="dot" style="background:{led_dot}"></span>
        <span>LED: <b>{led_duty_pct}%</b></span>
      </div>
      <div class="btns mt8">
        <a class="btn off small" href="/led?d=0">OFF</a>
        <a class="btn t small"   href="/led?d=50">50%</a>
        <a class="btn t small"   href="/led?d=80">80%</a>
        <a class="btn on small"  href="/led?d=100">100%</a>
      </div>
      <form action="/led" method="get" class="mt4">
        <label>듀티 <input name="d" type="number" step="5" min="0" max="100" value="{led_duty_pct}">%</label>
        <button class="btn t small">설정</button>
      </form>

      <hr style="border:0;border-top:1px solid #334155;margin:12px 0;">

      <div class="row">
        <span class="dot" style="background:{fan_dot}"></span>
        <span>팬: <b>{fan_duty_pct}%</b></span>
      </div>
      <div class="btns mt8">
        <a class="btn off small" href="/fan?d=0">OFF</a>
        <a class="btn t small"   href="/fan?d=30">30%</a>
        <a class="btn t small"   href="/fan?d=60">60%</a>
        <a class="btn on small"  href="/fan?d=100">100%</a>
      </div>
      <form action="/fan" method="get" class="mt4">
        <label>듀티 <input name="d" type="number" step="5" min="0" max="100" value="{fan_duty_pct}">%</label>
        <button class="btn t small">설정</button>
      </form>
    </div>"""

    # 수동 제어
    manual_rows = ""
    for i in range(4):
        manual_rows += f"""
        <div class="manual-row">
          <span class="dot" style="background:{_pump_status_dot(i)}"></span>
          <span><strong>{PUMP_LABELS[i]}</strong></span>
          <div class="btns">
            <a class="btn on small"  href="/pump/on?p={i}">ON</a>
            <a class="btn off small" href="/pump/off?p={i}">OFF</a>
            <a class="btn t small"   href="/pump/run?p={i}&s=3">3초</a>
          </div>
        </div>"""
    manual_card = f"""
    <div class="card">
      <h2>수동 제어 (디버깅)</h2>
      {manual_rows}
    </div>"""

    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{refresh}
<title>양액 조제 시스템</title>
<style>
 *{{box-sizing:border-box}}
 body{{font-family:-apple-system,Segoe UI,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:12px;max-width:560px;margin-left:auto;margin-right:auto;}}
 h1{{font-size:18px;margin:0 0 12px;}}
 h2{{font-size:15px;margin:0 0 8px;color:#cbd5e1;}}
 .card{{background:#1e293b;border-radius:12px;padding:12px;margin-bottom:10px;}}
 .row,.manual-row{{display:flex;align-items:center;gap:8px;}}
 .manual-row{{padding:6px 0;}}
 .manual-row .btns{{margin-left:auto;}}
 .dot{{width:10px;height:10px;border-radius:50%;display:inline-block;flex-shrink:0;}}
 .btns{{display:flex;gap:6px;flex-wrap:wrap;}}
 .btn{{padding:10px 12px;border-radius:8px;text-decoration:none;color:#fff;font-weight:600;font-size:14px;background:#475569;border:none;cursor:pointer;display:inline-block;text-align:center;}}
 .btn.big{{width:100%;padding:14px;font-size:16px;}}
 .btn.small{{padding:6px 10px;font-size:12px;}}
 .btn.on{{background:#16a34a;}} .btn.off{{background:#dc2626;}} .btn.t{{background:#2563eb;}}
 .btn[disabled],a.btn[disabled]{{opacity:.4;pointer-events:none;}}
 .status{{background:#312e81;border-radius:10px;padding:10px 12px;margin-bottom:10px;font-weight:600;display:flex;align-items:center;gap:10px;}}
 .status.busy{{background:#a16207;}}
 .status > span{{flex:1;}}
 .stop-inline{{flex-shrink:0;}}
 .recipe-show{{color:#94a3b8;font-size:13px;margin-bottom:8px;}}
 .muted{{color:#94a3b8;font-size:12px;}}
 input{{background:#0f172a;color:#e2e8f0;border:1px solid #475569;border-radius:6px;padding:6px 8px;width:90px;font-size:13px;}}
 label{{display:inline-flex;align-items:center;gap:6px;margin-right:8px;font-size:13px;}}
 .row3{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;}}
 .calib-row{{padding:8px 0;border-top:1px solid #334155;}}
 .calib-row:first-of-type{{border-top:none;}}
 details summary{{cursor:pointer;color:#94a3b8;font-size:13px;padding:6px 0;}}
 .mt4{{margin-top:4px;}} .mt8{{margin-top:8px;}}
 form{{margin:0;}}
</style></head>
<body>
<h1>양액 조제 시스템</h1>

<div class="status{(' busy' if busy else '')}">
  <span>{_status_display()}</span>
  {'<a class="btn off small stop-inline" href="/stop">중단</a>' if busy else ''}
</div>

{sensor_card}
{mix_card}
{stir_card}
{drain_card}
{led_fan_card}
{calib_card}
{manual_card}

<div class="card">
  <a class="btn off big" href="/stop">⛔ 비상정지 (모두 OFF)</a>
</div>
</body></html>"""


# ===== HTTP 라우팅 =====
def parse_query(path):
    if "?" not in path:
        return path, {}
    p, q = path.split("?", 1)
    params = {}
    for pair in q.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v.replace("+", " ")
    return p, params


def _intp(params, key, default=-1):
    try: return int(params.get(key, default))
    except Exception: return default


def _floatp(params, key, default=0.0):
    try: return float(params.get(key, default))
    except Exception: return default


def _status_json():
    """디스플레이용 시스템 상태 JSON. RP2350 + W5500 클라이언트가 폴링."""
    remaining = 0.0
    if step_duration_s > 0:
        elapsed = time.ticks_diff(time.ticks_ms(), step_start_ms) / 1000.0
        remaining = max(0.0, step_duration_s - elapsed)

    payload = {
        "busy": busy,
        "status_text": status_text,
        "step_remaining_s": round(remaining, 1),
        "pump_states": state,
        "pump_labels": PUMP_LABELS,
        "flow_ml_per_sec": [round(f, 3) for f in flow],
        "stirrer": stirrer_state,
        "led_pct": led_duty_pct,
        "fan_pct": fan_duty_pct,
        "recipe": recipe,
    }
    if SENSORS_AVAILABLE:
        sd = sensors.data
        payload["sensors"] = {
            "air_temp":  sd["air_temp"],
            "humidity":  sd["humidity"],
            "moisture":  sd["moisture"],
            "soil_temp": sd["soil_temp"],
            "soil_ec":   sd["soil_ec"],
            "soil_ph":   sd["soil_ph"],
            "n":         sd["n"],
            "p":         sd["p"],
            "k":         sd["k"],
            "sol_ec":    sd["sol_ec"],
            "sol_ph":    sd["sol_ph"],
            "age_s": {
                "th":   sensors.age_seconds("th"),
                "soil": sensors.age_seconds("soil"),
            },
        }
    return json.dumps(payload)


def handle(path):
    route, params = parse_query(path)

    # ===== JSON API (디스플레이/외부 클라이언트용) =====
    if route == "/api/status":
        return ("application/json", _status_json())
    if route == "/api/sensors" and SENSORS_AVAILABLE:
        return ("application/json", json.dumps(sensors.data))
    if route == "/api/recipe":
        return ("application/json", json.dumps(recipe))

    if route == "/stop":
        was_busy = busy
        abort_mix()
        if not was_busy:
            _set_step("정지됨")
        # busy 였으면 시퀀스 스레드가 finally 에서 "중단됨" 으로 갱신함

    elif route == "/mix":
        start_mix()

    elif route == "/pump/on":
        if not busy:
            i = _intp(params, "p")
            if 0 <= i < 4: pump_on(i)

    elif route == "/pump/off":
        i = _intp(params, "p")
        if 0 <= i < 4: pump_off(i)

    elif route == "/pump/run":
        if not busy:
            i = _intp(params, "p"); s = _floatp(params, "s", 3.0)
            if 0 <= i < 4: pump_run_async(i, s)

    elif route == "/dose":
        if not busy:
            i = _intp(params, "p"); ml = _floatp(params, "ml")
            if 0 <= i < 4: dose_async(i, ml)

    elif route == "/calib_run":
        if not busy:
            i = _intp(params, "p")
            s = _floatp(params, "s", DEFAULT_CALIB_SEC[i] if 0 <= i < 4 else 10.0)
            if 0 <= i < 4: calibrate_run(i, s)

    elif route == "/calib_start":
        if not busy:
            i = _intp(params, "p")
            if 0 <= i < 4: calibrate_manual_start(i)

    elif route == "/calib_stop":
        i = _intp(params, "p")
        if 0 <= i < 4: calibrate_manual_stop(i)

    elif route == "/calib_apply":
        i = _intp(params, "p"); ml = _floatp(params, "ml")
        if 0 <= i < 4: calibrate_apply(i, ml)

    elif route == "/recipe":
        w = _floatp(params, "water", -1)
        a = _floatp(params, "a", -1)
        b = _floatp(params, "b", -1)
        s = _floatp(params, "stir", -1)
        update_recipe(
            water=(w if w >= 0 else None),
            a=(a if a >= 0 else None),
            b=(b if b >= 0 else None),
            stir=(s if s >= 0 else None),
        )

    elif route == "/stir/on":
        if not busy:
            stirrer_on()

    elif route == "/stir/off":
        stirrer_off()

    elif route == "/stir/run":
        if not busy:
            s = _floatp(params, "s", 30.0)
            stirrer_run_async(s)

    elif route == "/led":
        d = _intp(params, "d", 0)
        led_set(d)

    elif route == "/fan":
        d = _intp(params, "d", 0)
        fan_set(d)

    return render()


def _send_all(sock, data):
    """MicroPython socket.send 가 partial send 가능. 끝까지 보내는 루프."""
    view = memoryview(data)
    total = len(view)
    off = 0
    while off < total:
        n = sock.send(view[off:])
        if n is None or n <= 0:
            break
        off += n


# ===== 서버 루프 (WiFi 재연결 + gc 포함) =====
GC_INTERVAL_MS    = 60_000   # 1분마다 gc.collect()
SOCKET_TIMEOUT_S  = 5.0      # 5초마다 한 번씩 WiFi 체크 가능하게


def _try_reconnect_wifi(wlan):
    """WiFi 끊김 감지 시 재연결 시도."""
    if wlan.isconnected():
        return True
    print("WiFi 끊김 — 재연결 시도...")
    try:
        wlan.disconnect()
    except Exception:
        pass
    try:
        wlan.connect(SSID, PASSWORD)
        for _ in range(15):
            if wlan.isconnected():
                ip = wlan.ifconfig()[0]
                print("WiFi 재연결됨:", ip)
                return True
            time.sleep(1)
    except Exception as e:
        print("재연결 실패:", e)
    return False


def serve(ip):
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(2)
    s.settimeout(SOCKET_TIMEOUT_S)   # 주기적 WiFi 체크용
    print(f"웹서버 시작: http://{ip}/")

    wlan = network.WLAN(network.STA_IF)
    last_gc_ms = time.ticks_ms()

    while True:
        # 1) 주기적 gc (메모리 단편화 방지)
        if time.ticks_diff(time.ticks_ms(), last_gc_ms) > GC_INTERVAL_MS:
            gc.collect()
            last_gc_ms = time.ticks_ms()
            print("gc free:", gc.mem_free())

        # 2) WiFi 끊김 감지 & 재연결
        if not wlan.isconnected():
            if not _try_reconnect_wifi(wlan):
                time.sleep(5)
                continue

        # 3) HTTP 요청 처리 (5초 타임아웃 → 위 WiFi 체크 주기적으로)
        cl = None
        try:
            cl, _addr = s.accept()
            req = cl.recv(2048).decode("utf-8", "ignore")
            try:
                path = req.split(" ", 2)[1]
            except IndexError:
                path = "/"
            result = handle(path)
            if isinstance(result, tuple):
                content_type, body_str = result
            else:
                content_type, body_str = "text/html; charset=utf-8", result
            body = body_str.encode("utf-8")
            header = ("HTTP/1.1 200 OK\r\n"
                      f"Content-Type: {content_type}\r\n"
                      f"Content-Length: {len(body)}\r\n"
                      "Connection: close\r\n\r\n").encode("utf-8")
            _send_all(cl, header)
            _send_all(cl, body)
        except OSError as e:
            # 타임아웃은 정상 (WiFi/gc 체크 루프로 복귀)
            err = e.args[0] if e.args else 0
            if err in (110, 11, 116):  # ETIMEDOUT, EAGAIN
                pass
            else:
                print("socket err:", e)
        except Exception as e:
            print("req err:", e)
        finally:
            if cl:
                try: cl.close()
                except Exception: pass


if __name__ == "__main__":
    load_persisted()
    ip = connect_wifi()

    # 하나의 백그라운드 스레드로 통합 (RP2040 MicroPython 안정성)
    _thread.start_new_thread(_bg_thread, ())
    print("백그라운드 스레드 시작 (센서 + 디스플레이 + 시퀀스 통합)")

    if ip is not None:
        serve(ip)
    else:
        # 오프라인: HTTP 비활성. 메인 스레드는 그냥 슬립.
        print("HTTP 비활성 (WiFi 실패). 펌프/센서/디스플레이/시퀀스는 정상 동작.")
        while True:
            time.sleep(30)
            gc.collect()
