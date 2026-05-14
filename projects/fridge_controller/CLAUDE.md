# Fridge Controller Context

When the user asks about "냉장고 온도조절 로직", answer from this document and the code in this folder.

## Short Answer To Give

냉장고 제어는 Pico/RP2040이 최종 판단한다. RP2350과 웹은 대시보드/리모컨 역할만 한다. 현재는 정상 확인된 RS485 온습도 센서 1개, 주소 `1`의 온도값만 사용한다.

자동제어는 목표온도와 `+/- 0.5 C` 히스테리시스 기반이다.

- 냉장고가 꺼져 있고 현재온도 >= 목표온도 + 0.5 C 이면 켜기를 요청한다.
- 냉장고가 켜져 있고 현재온도 <= 목표온도 - 0.5 C 이면 끄기를 요청한다.
- 그 사이에서는 현재 상태를 유지한다.

다만 컴프레셔 보호가 온도제어보다 우선이다.

- 최소 꺼짐 시간: 300초
- 최소 켜짐 시간: 300초

그래서 온도 조건이 맞아도 5분 보호시간이 남아 있으면 켜거나 끄지 않고 대기한다.

## Important State Flags

- `armed=0`: SSR 출력이 안전상 잠겨 있다.
- `armed=1`: SSR 출력이 허가되어 있다.
- `auto=0`: 온도 자동제어를 하지 않는다.
- `auto=1`: 온도 조건에 따라 냉장고를 켜고 끄려고 한다.

정상 자동 운전은 `armed=1`, `auto=1` 상태다. 현재 코드에서는 `auto 1` 명령을 보내면 자동으로 `armed=True`가 된다.

## Current Control Values

- Default target: `15.0 C`
- Target range: `0.0 C` to `25.0 C`
- Band: `+/- 0.5 C`
- Sensor read interval: 2 seconds
- RP2350 status interval: 2 seconds
- Minimum off: 300 seconds
- Minimum on: 300 seconds

## Hardware Pins

Pico/RP2040:

- `GP28`: XSSR DA2410 input `3 (+)`
- `GND`: XSSR input `4 (-)`
- `GP0/GP1`: sensor RS485 UART0
- `GP4/GP5`: RP2350 RS485 UART1
- `GP20`: RP2350 RS485 DE/RE direction
- `GP16`: LED MOSFET PWM
- `GP18`: fan MOSFET PWM

XSSR 220V side:

- XSSR `1/2` switch only the AC live line.
- Neutral and earth pass through directly.
- Never mix 220V wiring with Pico/RP2350 low-voltage wiring.

## Fan And LED

Fan and LED are MOSFET outputs. Fan is treated as on/off because the current fan does not meaningfully change speed across the PWM range. LED remains PWM.

Commands:

```text
fan 0
fan 100
led <0..100>
```

Status:

```text
fan=<0|100> led=<0..100>
```

Defaults:

- fan: 0%
- led: 0%

## Current Files

- Pico controller: `fridge_controller/controller/pico_wh/main.py`
- Web controller: `fridge_controller/tools/web_controller.py`
- Raspberry Pi fridge gateway: `fridge_controller/gateway/fridge_gateway_server.py`
- Fridge DB setup: `fridge_controller/gateway/setup_fridge_db.py`
- RP2350 dashboard: `RP2350-Touch-LCD-4/examples/fridge_dashboard/fridge_dashboard.c`
- Development log: `fridge_controller/docs/06_TEST_LOG.md`

## Raspberry Pi Gateway

Preferred logging architecture:

```text
Pico WH -> Wi-Fi -> Raspberry Pi HTTP POST /fridge -> MariaDB fridge_readings
```

Do not put MariaDB protocol/client logic directly on Pico unless explicitly requested. Keep Pico responsible for control and HTTP POST only; keep DB credentials and INSERT logic on Raspberry Pi.

As of 2026-05-08, Pico WH Wi-Fi logging is integrated into `fridge_controller/controller/pico_wh/main.py`.

- Gateway: `192.168.100.30:8081/fridge`
- Logging table: `fridge_readings`
- Logging period: 1 second
- Required Pico firmware: Pico W MicroPython with `network` module
- Wi-Fi credentials live in `wifi_config.py`, which is ignored by git.

Dashboard at `http://192.168.100.30:8081/` has two tabs:

- Real-time status: latest row and recent 10 minute mini chart.
- Data analysis: range filter, ECharts temperature/target/SSR chart, summary cards, row table.

## RP2350 Responsiveness

RP2350 dashboard uses optimistic local UI updates:

- Touch callbacks update the RP2350 screen immediately.
- UART writes are not performed directly inside touch callbacks.
- Commands are queued and sent from the main loop.
- Repeated target/fan/LED changes keep only the newest value.
- Pico `STATUS` later confirms or corrects the local display.
- Countdown fields such as `wait_on_s`, `wait_off_s`, and `state_elapsed_s` are received as baselines from Pico, then counted locally on RP2350 between status frames.

## Things Intentionally Not Implemented Yet

- Two-sensor averaging
- Sensor disagreement monitoring
- Sensor error fail-safe policy
- More complex PID-style control

The user explicitly decided to keep those out for now and proceed with one confirmed working sensor.
