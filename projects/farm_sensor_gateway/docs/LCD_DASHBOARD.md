# RP2350 Touch LCD 4 대시보드 설계 문서

## 목표
Waveshare RP2350-Touch-LCD-4 보드를 RS485 버스에 passive listener로 연결,
기존 RP2040이 수집하는 센서 데이터를 4인치 LCD에 실시간 대시보드로 표시.

---

## 하드웨어

### Waveshare RP2350-Touch-LCD-4 스펙
- MCU: RP2350B (ARM Cortex-M33 듀얼코어, 최대 150MHz, 실제 240MHz 오버클럭 가능)
- LCD: 480×480 IPS, ST7701 드라이버, RGB 인터페이스
- 터치: GT911 (I2C, 5포인트 정전식)
- 온보드: RS485, CAN, I2C, IMU(QMI8658), RTC(PCF85063), TF카드슬롯
- Flash: 16MB / SRAM: 520KB

### RS485 핀 정보
- RS485 IC: **SP3485EN** (U7)
- 방향 제어: **자동** — Q2 트랜지스터가 TXD1 신호로 DE/RE 자동 전환
  - TXD1 idle(HIGH) → 수신 모드 자동 유지
  - 별도 DE/RE GPIO 제어 불필요
  - Passive listen = UART TX 사용 안 하면 됨
- 레벨 시프터: SN74LVC1G125DBVR (U13, 3.3V 대응)
- 외부 단자 공유: SW1 물리 스위치로 CAN/RS485 전환 (RS485 사용 시 핀 2-3)
- **TXD1 → GP8** (UART1 TX, passive listen 시 사용 안 함)
- **RXD1 → GP9** (UART1 RX)
- 출처: examples/rs485/rs485.c

---

## 아키텍처

```
[RS485 버스 A/B]
      │
      ├── RP2040 Zero  (마스터: 쿼리 전송 + W5500 HTTP POST, 기존 그대로)
      │
      └── RP2350 Touch LCD 4  (수신 전용, DE=0 고정 → passive listen)
                │
                └── Modbus 응답 패킷 파싱 → LVGL 대시보드 표시
```

### Passive Listen 원리
RS485 트랜시버 IC의 DE(Driver Enable) 핀을 LOW로 고정하면 송신 회로가 차단됨.
RP2040이 쿼리 → 센서 응답 → RP2350B도 같은 응답 신호 수신 가능.
두 보드 간 충돌 없음, 기존 RP2040 코드 변경 불필요.

---

## 구현 방향

| 항목 | 결정 |
|---|---|
| 언어 | C/C++ (MicroPython은 LVGL 성능 부족) |
| UI 라이브러리 | LVGL (보드 예제에 이미 통합) |
| 데이터 수신 | RS485 passive listen |
| 화면 구성 | 센서 카드 레이아웃 (아래 참고) |

---

## 화면 레이아웃 (초안)

```
┌─────────────────────────────┐
│  Hunet  [●LIVE]  [시각]     │  ← 헤더
├──────────┬──────────────────┤
│ 공기                        │
│ 🌡 Air   💧 Humidity        │
│ 23.5°C   36.4%              │
├──────────────────────────────┤
│ 토양                        │
│ Moisture SoilTemp EC   pH   │
│ 18.5%    21.9°C   93  5.7  │
│ N:3  P:6  K:15              │
├──────────────────────────────┤
│ ☀ Solar       CO2           │
│ 450 W/m²      700 ppm       │
├──────────────────────────────┤
│ 팬 릴레이: OFF              │
└─────────────────────────────┘
```

---

## 표시할 센서 항목 (11개)

| 변수 | 단위 | 센서 주소 |
|---|---|---|
| air_temp | °C | 0x01 |
| humidity | % | 0x01 |
| moisture | % | 0x02 |
| soil_temp | °C | 0x02 |
| ec | µS/cm | 0x02 |
| ph | - | 0x02 |
| n | mg/kg | 0x02 |
| p | mg/kg | 0x02 |
| k | mg/kg | 0x02 |
| solar | W/m² | 0x03 |
| co2 | ppm | 0x04 |

---

## Modbus 패킷 파싱 방식

RP2040이 각 센서에 쿼리를 보내면 센서가 응답.
RP2350B는 응답 패킷의 첫 바이트(slave address)로 어느 센서인지 판별.

```
응답 패킷 구조 (FC=0x03):
[addr] [0x03] [byte_count] [data...] [CRC_LO] [CRC_HI]

예) 온습도 센서 (addr=0x01) 응답:
01 03 04 01 68 00 EB ...
         └──┘ └──┘
       습도÷10  온도÷10
```

---

## 남은 확인 사항

- [ ] RS485 GPIO 핀 번호 (회로도 or rs485 예제 코드)
- [ ] DE/RE 핀 제어 방식
- [ ] LVGL 버전 (보드 예제 기준)
- [ ] RP2040 쿼리 주기 (현재 2초) — 파싱 타임아웃 설정에 필요

---

## 개발 환경

- IDE: VSCode + pico-vscode 플러그인
- SDK: Pico C SDK (RP2350B 타겟)
- UI: LVGL (보드 제공 라이브러리 그대로 사용)
- 예제 참고: `examples/rs485/`, `examples/lvgl/`
