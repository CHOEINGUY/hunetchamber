from machine import Pin, PWM, UART
import json
import sys
import time

try:
    import uselect as select
except ImportError:
    import select

try:
    import network
    import socket
except ImportError:
    network = None
    socket = None

try:
    from wifi_config import WIFI_SSID, WIFI_PASSWORD
except ImportError:
    WIFI_SSID = None
    WIFI_PASSWORD = None


FRIDGE_PIN = 28
LED_PIN = 16
FAN_PIN = 18
RP2350_DIR_PIN = 20

FRIDGE_ACTIVE_HIGH = True
MIN_OFF_SECONDS = 300
MIN_ON_SECONDS = 300
SENSOR_READ_MS = 1000
RP2350_STATUS_MS = SENSOR_READ_MS
CONTROL_BAND_C = 0.5
DEFAULT_TARGET_C = 15.0
TARGET_STEP_C = 0.5
TARGET_MIN_C = 0.0
TARGET_MAX_C = 25.0

SENSOR_ADDRESSES = (1,)
DEVICE_ID = "fridge-01"
GATEWAY_HOST = "192.168.100.30"
GATEWAY_PORT = 8081
GATEWAY_PATH = "/fridge"
GATEWAY_POST_MS = 1000
WIFI_RETRY_MS = 30000
WIFI_CONNECT_TIMEOUT_MS = 15000
HTTP_TIMEOUT_SECONDS = 2


fridge = Pin(FRIDGE_PIN, Pin.OUT)
led_pwm = PWM(Pin(LED_PIN))
fan_pwm = PWM(Pin(FAN_PIN))
led_pwm.freq(1000)
fan_pwm.freq(20000)
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=80)
rp2350_dir = Pin(RP2350_DIR_PIN, Pin.OUT, value=0)
rp2350_uart = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5), timeout=20)

fridge_on_state = False
armed = False
auto_mode = False
target_c = DEFAULT_TARGET_C
fan_percent = 0
led_percent = 0

min_off_ms = MIN_OFF_SECONDS * 1000
min_on_ms = MIN_ON_SECONDS * 1000
last_off_ms = time.ticks_add(time.ticks_ms(), -min_off_ms)
last_on_ms = time.ticks_add(time.ticks_ms(), -min_on_ms)
last_sensor_read_ms = time.ticks_add(time.ticks_ms(), -SENSOR_READ_MS)
last_rp2350_status_ms = time.ticks_add(time.ticks_ms(), -RP2350_STATUS_MS)
last_gateway_post_ms = time.ticks_ms()
last_wifi_attempt_ms = time.ticks_add(time.ticks_ms(), -WIFI_RETRY_MS)

sensors = [
    {"addr": SENSOR_ADDRESSES[0], "temp": None, "humidity": None, "ok_ms": None},
]
current_temp_c = None
current_humidity = None
last_control_reason = "boot"
wlan = None
wifi_connecting = False
last_gateway_result = "not_started"
usb_command_buf = ""


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


def value_or_na(value):
    if value is None:
        return "na"
    return "{:.1f}".format(value)


def json_value(value):
    if value is None:
        return None
    return value


def clamp(value, low, high):
    return min(max(value, low), high)


def quantize_target(value):
    value = clamp(value, TARGET_MIN_C, TARGET_MAX_C)
    return round(value / TARGET_STEP_C) * TARGET_STEP_C


def set_pwm_percent(pwm, percent):
    percent = int(clamp(percent, 0, 100))
    pwm.duty_u16((percent * 65535) // 100)
    return percent


def set_fan_percent(percent):
    global fan_percent
    fan_percent = set_pwm_percent(fan_pwm, 100 if int(percent) > 0 else 0)
    return fan_percent


def set_led_percent(percent):
    global led_percent
    led_percent = set_pwm_percent(led_pwm, percent)
    return led_percent


def write_fridge(on):
    global fridge_on_state, last_off_ms, last_on_ms
    fridge.value(1 if (on == FRIDGE_ACTIVE_HIGH) else 0)
    if not fridge_on_state and on:
        last_on_ms = time.ticks_ms()
    if fridge_on_state and not on:
        last_off_ms = time.ticks_ms()
    fridge_on_state = on


def seconds_until_on_allowed():
    elapsed = time.ticks_diff(time.ticks_ms(), last_off_ms)
    remaining = min_off_ms - elapsed
    if remaining <= 0:
        return 0
    return (remaining + 999) // 1000


def seconds_until_off_allowed():
    if not fridge_on_state:
        return 0
    elapsed = time.ticks_diff(time.ticks_ms(), last_on_ms)
    remaining = min_on_ms - elapsed
    if remaining <= 0:
        return 0
    return (remaining + 999) // 1000


def state_elapsed_seconds():
    if fridge_on_state:
        return time.ticks_diff(time.ticks_ms(), last_on_ms) // 1000
    return time.ticks_diff(time.ticks_ms(), last_off_ms) // 1000


def sensor_age_seconds(sensor):
    if sensor["ok_ms"] is None:
        return -1
    return time.ticks_diff(time.ticks_ms(), sensor["ok_ms"]) // 1000


def read_temp_humidity(addr):
    while uart.any():
        uart.read()
    uart.write(make_read(addr, 0x0000, 2))
    time.sleep_ms(250)
    resp = uart.read() if uart.any() else None

    if not resp or len(resp) < 9:
        return None
    body = resp[:-2]
    got_crc = resp[-2] | (resp[-1] << 8)
    if crc16(body) != got_crc:
        return None
    if resp[0] != addr or resp[1] != 0x03:
        return None

    humidity = ((resp[3] << 8) | resp[4]) / 10.0
    raw_temp = (resp[5] << 8) | resp[6]
    if raw_temp & 0x8000:
        raw_temp -= 0x10000
    temp = raw_temp / 10.0
    if not (-40.0 <= temp <= 80.0) or not (0.0 <= humidity <= 100.0):
        return None
    return temp, humidity


def update_current_sensor_values():
    global current_temp_c, current_humidity
    current_temp_c = sensors[0]["temp"]
    current_humidity = sensors[0]["humidity"]


def maybe_read_sensors():
    global last_sensor_read_ms
    if time.ticks_diff(time.ticks_ms(), last_sensor_read_ms) < SENSOR_READ_MS:
        return
    last_sensor_read_ms = time.ticks_ms()

    for sensor in sensors:
        reading = read_temp_humidity(sensor["addr"])
        if reading:
            sensor["temp"], sensor["humidity"] = reading
            sensor["ok_ms"] = time.ticks_ms()
            print("SENSOR{} temp_c={} humidity={}".format(
                sensor["addr"],
                value_or_na(sensor["temp"]),
                value_or_na(sensor["humidity"]),
            ))
        else:
            print("SENSOR{} error".format(sensor["addr"]))
    update_current_sensor_values()


def try_turn_on(reason):
    global last_control_reason
    wait_s = seconds_until_on_allowed()
    if wait_s:
        last_control_reason = "{}_wait_on_{}s".format(reason, wait_s)
        return False
    write_fridge(True)
    last_control_reason = reason
    return True


def try_turn_off(reason):
    global last_control_reason
    wait_s = seconds_until_off_allowed()
    if wait_s:
        last_control_reason = "{}_wait_off_{}s".format(reason, wait_s)
        return False
    write_fridge(False)
    last_control_reason = reason
    return True


def apply_auto_control():
    global last_control_reason
    if not auto_mode:
        return
    if current_temp_c is None:
        last_control_reason = "no_temp"
        return

    upper = target_c + CONTROL_BAND_C
    lower = target_c - CONTROL_BAND_C

    if not fridge_on_state and current_temp_c >= upper:
        try_turn_on("auto_temp_high")
    elif fridge_on_state and current_temp_c <= lower:
        try_turn_off("auto_temp_low")
    else:
        last_control_reason = "auto_hold"


def status_line():
    return (
        "STATUS on={} armed={} auto={} target_c={} band_c={} "
        "min_off_s={} wait_on_s={} min_on_s={} wait_off_s={} state_elapsed_s={} "
        "temp_c={} humidity={} sensor_age_s={} fan={} led={} reason={}".format(
            1 if fridge_on_state else 0,
            1 if armed else 0,
            1 if auto_mode else 0,
            value_or_na(target_c),
            value_or_na(CONTROL_BAND_C),
            min_off_ms // 1000,
            seconds_until_on_allowed(),
            min_on_ms // 1000,
            seconds_until_off_allowed(),
            state_elapsed_seconds(),
            value_or_na(current_temp_c),
            value_or_na(current_humidity),
            sensor_age_seconds(sensors[0]),
            fan_percent,
            led_percent,
            last_control_reason,
        )
    )


def fridge_payload():
    return {
        "device_id": DEVICE_ID,
        "temp_c": json_value(current_temp_c),
        "humidity": json_value(current_humidity),
        "target_c": target_c,
        "band_c": CONTROL_BAND_C,
        "fridge_on": 1 if fridge_on_state else 0,
        "armed": 1 if armed else 0,
        "auto_mode": 1 if auto_mode else 0,
        "fan_percent": fan_percent,
        "led_percent": led_percent,
        "min_off_s": min_off_ms // 1000,
        "wait_on_s": seconds_until_on_allowed(),
        "min_on_s": min_on_ms // 1000,
        "wait_off_s": seconds_until_off_allowed(),
        "state_elapsed_s": state_elapsed_seconds(),
        "sensor_age_s": sensor_age_seconds(sensors[0]),
        "reason": last_control_reason,
    }


def print_status():
    print(status_line())


def send_rp2350_line(line):
    rp2350_dir.value(1)
    time.sleep_ms(2)
    rp2350_uart.write((line + "\n").encode())
    try:
        rp2350_uart.flush()
    except AttributeError:
        time.sleep_ms(20)
    time.sleep_ms(2)
    rp2350_dir.value(0)


def maybe_send_rp2350_status():
    global last_rp2350_status_ms
    if time.ticks_diff(time.ticks_ms(), last_rp2350_status_ms) < RP2350_STATUS_MS:
        return
    last_rp2350_status_ms = time.ticks_ms()
    send_rp2350_line(status_line())


def check_rp2350_commands():
    rp2350_dir.value(0)
    while rp2350_uart.any():
        try:
            line = rp2350_uart.readline()
        except AttributeError:
            line = rp2350_uart.read()
        if not line:
            return
        try:
            text = line.decode().strip()
        except Exception:
            continue
        if text:
            print("RP2350 CMD {}".format(text))
            handle_command(text)
            if text.lower().split()[0] == "status":
                send_rp2350_line(status_line())


def parse_float(text):
    try:
        return float(text)
    except ValueError:
        return None


def wifi_available():
    return network is not None and socket is not None and WIFI_SSID and WIFI_PASSWORD


def wifi_connected():
    return wlan is not None and wlan.isconnected()


def maybe_connect_wifi():
    global wlan, wifi_connecting, last_wifi_attempt_ms, last_gateway_result

    if not wifi_available():
        last_gateway_result = "wifi_not_configured"
        return False
    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    if wlan.isconnected():
        wifi_connecting = False
        return True

    now = time.ticks_ms()
    if wifi_connecting:
        if time.ticks_diff(now, last_wifi_attempt_ms) > WIFI_CONNECT_TIMEOUT_MS:
            wifi_connecting = False
            last_gateway_result = "wifi_timeout"
        return False

    if time.ticks_diff(now, last_wifi_attempt_ms) < WIFI_RETRY_MS:
        return False

    last_wifi_attempt_ms = now
    wifi_connecting = True
    last_gateway_result = "wifi_connecting"
    try:
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    except Exception as exc:
        wifi_connecting = False
        last_gateway_result = "wifi_error_{}".format(type(exc).__name__)
    return False


def post_gateway_payload(payload):
    body = json.dumps(payload)
    request = (
        "POST {} HTTP/1.1\r\n"
        "Host: {}\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n"
        "\r\n"
        "{}"
    ).format(GATEWAY_PATH, GATEWAY_HOST, len(body), body)

    addr = socket.getaddrinfo(GATEWAY_HOST, GATEWAY_PORT)[0][-1]
    s = socket.socket()
    try:
        s.settimeout(HTTP_TIMEOUT_SECONDS)
        s.connect(addr)
        s.send(request.encode())
        resp = s.recv(96)
        return resp and b"200" in resp
    finally:
        s.close()


def maybe_post_gateway():
    global last_gateway_post_ms, last_gateway_result
    if time.ticks_diff(time.ticks_ms(), last_gateway_post_ms) < GATEWAY_POST_MS:
        return
    last_gateway_post_ms = time.ticks_ms()

    if not maybe_connect_wifi():
        return
    try:
        if post_gateway_payload(fridge_payload()):
            last_gateway_result = "post_ok"
            print("GATEWAY post_ok")
        else:
            last_gateway_result = "post_bad_response"
            print("GATEWAY post_bad_response")
    except Exception as exc:
        last_gateway_result = "post_error_{}".format(type(exc).__name__)
        print("GATEWAY {}".format(last_gateway_result))


def handle_command(line):
    global armed, auto_mode, target_c, min_off_ms, min_on_ms

    parts = line.strip().lower().split()
    if not parts:
        return

    cmd = parts[0]

    if cmd == "help":
        print("COMMANDS: status arm disarm on off forceoff auto <0|1> target <0..25> fan <0|100> led <0..100> minoff <seconds> minon <seconds>")
    elif cmd == "status":
        print_status()
    elif cmd == "arm":
        armed = True
        print("OK armed")
    elif cmd == "disarm":
        if try_turn_off("manual_disarm"):
            armed = False
            auto_mode = False
            print("OK disarmed and off")
        else:
            print("ERR minimum on time wait_s={}".format(seconds_until_off_allowed()))
    elif cmd == "on":
        if not armed:
            print("ERR not armed. Send: arm")
        elif try_turn_on("manual_on"):
            print("OK on")
        else:
            print("ERR compressor delay wait_s={}".format(seconds_until_on_allowed()))
    elif cmd == "off":
        if try_turn_off("manual_off"):
            print("OK off")
        else:
            print("ERR minimum on time wait_s={}".format(seconds_until_off_allowed()))
    elif cmd == "forceoff":
        write_fridge(False)
        armed = False
        auto_mode = False
        print("OK forceoff disarmed")
    elif cmd == "auto":
        if len(parts) != 2 or parts[1] not in ("0", "1"):
            print("ERR usage: auto <0|1>")
            return
        auto_mode = parts[1] == "1"
        if auto_mode:
            armed = True
        print("OK auto={}".format(1 if auto_mode else 0))
    elif cmd == "target":
        if len(parts) != 2:
            print("ERR usage: target <0..25>")
            return
        value = parse_float(parts[1])
        if value is None:
            print("ERR target must be a number")
            return
        target_c = quantize_target(value)
        print("OK target_c={}".format(value_or_na(target_c)))
    elif cmd == "fan":
        if len(parts) != 2:
            print("ERR usage: fan <0|100>")
            return
        try:
            percent = int(parts[1])
        except ValueError:
            print("ERR fan must be 0 or 100")
            return
        print("OK fan={}".format(set_fan_percent(percent)))
    elif cmd == "led":
        if len(parts) != 2:
            print("ERR usage: led <0..100>")
            return
        try:
            percent = int(parts[1])
        except ValueError:
            print("ERR led must be 0..100")
            return
        print("OK led={}".format(set_led_percent(percent)))
    elif cmd == "minoff":
        if len(parts) != 2:
            print("ERR usage: minoff <seconds>")
            return
        try:
            seconds = int(parts[1])
        except ValueError:
            print("ERR seconds must be an integer")
            return
        min_off_ms = clamp(seconds, 0, 3600) * 1000
        print("OK min_off_s={}".format(min_off_ms // 1000))
    elif cmd == "minon":
        if len(parts) != 2:
            print("ERR usage: minon <seconds>")
            return
        try:
            seconds = int(parts[1])
        except ValueError:
            print("ERR seconds must be an integer")
            return
        min_on_ms = clamp(seconds, 0, 3600) * 1000
        print("OK min_on_s={}".format(min_on_ms // 1000))
    else:
        print("ERR unknown command. Send: help")

    send_rp2350_line(status_line())


def check_usb_commands():
    global usb_command_buf
    while poll.poll(0):
        ch = sys.stdin.read(1)
        if ch in ("\r", "\n"):
            line = usb_command_buf
            usb_command_buf = ""
            handle_command(line)
        elif ch:
            usb_command_buf += ch
            if len(usb_command_buf) > 80:
                usb_command_buf = ""


write_fridge(False)
set_fan_percent(fan_percent)
set_led_percent(led_percent)
poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

print("fridge_controller ready")
print("Pico pins: sensors UART0 GP0/GP1, RP2350 UART1 GP4/GP5 dir GP20, fridge GP28, led GP16, fan GP18")
maybe_connect_wifi()
maybe_read_sensors()
print_status()

while True:
    maybe_read_sensors()
    apply_auto_control()
    check_rp2350_commands()
    maybe_send_rp2350_status()
    maybe_connect_wifi()
    maybe_post_gateway()
    check_usb_commands()
    time.sleep_ms(50)
