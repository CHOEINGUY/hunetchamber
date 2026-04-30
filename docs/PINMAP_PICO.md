# 핀맵 — Raspberry Pi Pico (일반)

펌웨어: `firmware/pico/main.py`

---

## 전체 연결 요약

| GPIO | 연결 대상 | 설명 |
|------|-----------|------|
| GP0  | RS485 모듈 RX | UART0 TX (Modbus 송신) |
| GP1  | RS485 모듈 TX | UART0 RX (Modbus 수신) |
| GP2  | 릴레이 모듈 IN | 릴레이 제어 |
| GP6  | RP2350 SDA | I2C 디스플레이 데이터 |
| GP7  | RP2350 SCL | I2C 디스플레이 클럭 |
| GP16 | W5500 MISO | SPI0 RX |
| GP17 | W5500 CS   | W5500 칩셀렉 |
| GP18 | W5500 SCK  | SPI0 클럭 |
| GP19 | W5500 MOSI | SPI0 TX |
| GP20 | W5500 RST  | W5500 리셋 |
| GP25 | 온보드 LED  | 내장 LED (상태 표시) |

---

## RS485 (Modbus RTU)

| Pico | RS485 모듈 |
|------|-----------|
| GP0  | RX (모듈 수신핀) |
| GP1  | TX (모듈 송신핀) |
| 5V   | VCC |
| GND  | GND |

- UART0, 9600 baud
- 센서 주소: 온습도 0x01 / 토양 0x02 / 조도 0x03 / CO2 0x04

---

## W5500 (Ethernet)

| W5500 | Pico GPIO |
|-------|-----------|
| SCK   | GP18 |
| MOSI  | GP19 |
| MISO  | GP16 |
| CS    | GP17 |
| RST   | GP20 |
| VCC   | 외부 3.3V (벅컨버터) |
| GND   | GND |

- 하드웨어 SPI0, baudrate=1_000_000, polarity=1, phase=1
- **주의**: Pico 3.3V핀 직접 연결 시 전압 드롭 발생 → 반드시 외부 벅컨버터 3.3V 사용

---

## RP2350 Touch LCD 4 (I2C 디스플레이)

| Pico | RP2350 커넥터 |
|------|--------------|
| GP6  | SDA |
| GP7  | SCL |
| GND  | GND |

- SoftI2C, freq=100_000, 슬레이브 주소 0x42
- VCC 연결 금지 (각자 전원 독립)

---

## 릴레이

| Pico | 릴레이 모듈 |
|------|-----------|
| GP2  | IN |
| 5V   | VCC |
| GND  | GND |

- 온도 > 30°C 시 자동 ON

---

## 전원 구성

| 항목 | 전원 |
|------|------|
| Pico | PC USB 또는 5V |
| 센서 4종 | 12V SMPS |
| W5500 | 벅컨버터 3.3V 출력 |
| GND | SMPS / Pico / W5500 / 벅컨버터 모두 공통 |
