# 핀맵 — Seeed XIAO RP2040

펌웨어: `firmware/xiao/main.py`

---

## 전체 연결 요약

| XIAO 핀 | GPIO | 연결 대상 | 설명 |
|---------|------|-----------|------|
| D6      | GP0  | RS485 모듈 RX | UART0 TX (Modbus 송신) |
| D7      | GP1  | RS485 모듈 TX | UART0 RX (Modbus 수신) |
| D8      | GP2  | 릴레이 모듈 IN | 릴레이 제어 |
| D10     | GP3  | W5500 MOSI | SoftSPI TX |
| D9      | GP4  | W5500 MISO | SoftSPI RX |
| D4      | GP6  | RP2350 SDA | I2C 디스플레이 데이터 |
| D5      | GP7  | RP2350 SCL | I2C 디스플레이 클럭 |
| D0      | GP26 | W5500 SCK  | SoftSPI 클럭 |
| D2      | GP28 | W5500 RST  | W5500 리셋 |
| D3      | GP29 | W5500 CS   | W5500 칩셀렉 |
| 3V3     | -    | -          | W5500 직접 연결 금지 (벅컨버터 사용) |
| GND     | -    | 공통 GND   | 모든 모듈 GND 공통 |

---

## RS485 (Modbus RTU)

| XIAO | RS485 모듈 |
|------|-----------|
| GP0 (D6) | RX (모듈 수신핀) |
| GP1 (D7) | TX (모듈 송신핀) |
| 5V | VCC |
| GND | GND |

- UART0, 9600 baud
- 센서 주소: 온습도 0x01 / 토양 0x02 / 조도 0x03 / CO2 0x04

---

## W5500 (Ethernet)

| W5500 | XIAO | GPIO |
|-------|------|------|
| SCK   | D0   | GP26 |
| MOSI  | D10  | GP3  |
| MISO  | D9   | GP4  |
| CS    | D3   | GP29 |
| RST   | D2   | GP28 |
| VCC   | 외부 3.3V (벅컨버터) | - |
| GND   | GND  | -    |

- SoftSPI, baudrate=100_000, polarity=1, phase=1
- **주의**: Pico 3.3V핀 직접 연결 시 전압 드롭 발생 → 반드시 외부 벅컨버터 3.3V 사용

---

## RP2350 Touch LCD 4 (I2C 디스플레이)

| XIAO | RP2350 커넥터 |
|------|--------------|
| GP6 (D4) | SDA |
| GP7 (D5) | SCL |
| GND | GND |

- SoftI2C, freq=100_000, 슬레이브 주소 0x42
- VCC 연결 금지 (각자 전원 독립)

---

## 릴레이

| XIAO | 릴레이 모듈 |
|------|-----------|
| GP2 (D8) | IN |
| 5V | VCC |
| GND | GND |

- 온도 > 30°C 시 자동 ON

---

## 전원 구성

| 항목 | 전원 |
|------|------|
| XIAO | PC USB 또는 5V |
| 센서 4종 | 12V SMPS |
| W5500 | 벅컨버터 3.3V 출력 |
| GND | SMPS / XIAO / W5500 / 벅컨버터 모두 공통 |
