# W5500 핀맵 — XIAO RP2040 / 일반 Pico

이 문서는 현재 실제 배선 기준이다.

현재 배선은 하드웨어 SPI의 고정 핀 조합이 아니므로 `machine.SoftSPI`를 사용한다.

## W5500 연결

| W5500 핀 | XIAO 핀 | GPIO | MicroPython 설정 | 설명 |
|----------|---------|------|------------------|------|
| SCK      | D0      | GP26 | `sck=Pin(26)`    | SPI clock |
| MO/MOSI  | D10     | GP3  | `mosi=Pin(3)`    | Master Out / W5500 In |
| MI/MISO  | D9      | GP4  | `miso=Pin(4)`    | Master In / W5500 Out |
| CS       | D3      | GP29 | `cs=Pin(29)`     | Chip select |
| RST      | D2      | GP28 | `rst=Pin(28)`    | Reset |
| INT      | -       | -    | -                | 미사용 |
| V        | 외부 3.3V | -  | -                | 벅 컨버터 3.3V 출력 |
| G        | 공통 GND | -  | -                | Pico GND와 벅 컨버터 GND 공통 |

## 전원

USR-ES1은 3.3V 전용 모듈이다. 5V를 넣으면 안 된다.

기존 Pico 3.3V 핀에서는 W5500 전원 전압이 약 2.7V까지 떨어졌으므로, 현재는 벅 컨버터를 3.3V로 세팅해서 W5500에 직접 공급한다.

전원 연결 기준:

| 연결 | 설명 |
|------|------|
| 벅 컨버터 3.3V OUT | W5500 V |
| 벅 컨버터 GND | W5500 G |
| Pico GND | W5500 G / 벅 컨버터 GND와 공통 |

Pico와 W5500의 GND는 반드시 공통이어야 한다. SPI 신호선만 연결하고 GND가 공통이 아니면 통신이 불안정하거나 동작하지 않는다.

## MicroPython 설정

```python
from machine import SoftSPI, Pin

spi = SoftSPI(
    baudrate=100_000,
    polarity=1,
    phase=1,
    sck=Pin(26),
    mosi=Pin(3),
    miso=Pin(4),
)
cs = Pin(29, Pin.OUT)
rst = Pin(28, Pin.OUT)
```

## 중요

`SCK=GP26`, `MOSI=GP3`, `MISO=GP4`는 RP2040 하드웨어 SPI의 같은 버스 핀 조합이 아니다. 따라서 `SPI(0, ...)` 또는 `SPI(1, ...)`로 잡으면 안 되고, 현재 코드처럼 `SoftSPI(...)`를 사용해야 한다.

현재 W5500은 `baudrate=100_000`, `polarity=1`, `phase=1`에서 VERSION 레지스터 `0x04`가 확인되었다. `500_000` 이상에서는 SPI 응답이 깨졌다.

## 전체 핀 사용 현황 (XIAO)

| XIAO 핀 | GPIO | 용도 |
|---------|------|------|
| D0      | GP26 | W5500 SCK |
| D1      | GP27 | 여유 |
| D2      | GP28 | W5500 RST |
| D3      | GP29 | W5500 CS |
| D4      | GP6  | I2C SDA (RP2350 디스플레이) |
| D5      | GP7  | I2C SCL (RP2350 디스플레이) |
| D6      | GP0  | RS485 TX |
| D7      | GP1  | RS485 RX |
| D8      | GP2  | 릴레이 |
| D9      | GP4  | W5500 MISO |
| D10     | GP3  | W5500 MOSI |
| 3V3     | -    | W5500에는 직접 공급하지 않음 |
| GND     | -    | W5500/벅 컨버터와 공통 접지 |

---

## Raspberry Pi Pico (일반) — W5500 연결

펌웨어: `firmware/pico/main.py`

하드웨어 SPI0 사용 (`baudrate=1_000_000`, `polarity=1`, `phase=1`)

| W5500 핀 | Pico 핀 | GPIO | 설명 |
|----------|---------|------|------|
| SCK      | GP18    | GP18 | SPI0 Clock |
| MOSI     | GP19    | GP19 | SPI0 TX |
| MISO     | GP16    | GP16 | SPI0 RX |
| CS       | GP17    | GP17 | Chip Select |
| RST      | GP20    | GP20 | Reset |
| VCC      | 외부 3.3V | -  | 벅 컨버터 3.3V (XIAO와 동일) |
| GND      | GND     | -    | 공통 GND |

### 전체 핀 사용 현황 (일반 Pico)

| GPIO | 용도 |
|------|------|
| GP0  | RS485 TX (UART0) |
| GP1  | RS485 RX (UART0) |
| GP2  | 릴레이 |
| GP6  | I2C SDA (RP2350 디스플레이) |
| GP7  | I2C SCL (RP2350 디스플레이) |
| GP16 | W5500 MISO (SPI0 RX) |
| GP17 | W5500 CS |
| GP18 | W5500 SCK (SPI0 CLK) |
| GP19 | W5500 MOSI (SPI0 TX) |
| GP20 | W5500 RST |
| GP25 | 온보드 LED |
