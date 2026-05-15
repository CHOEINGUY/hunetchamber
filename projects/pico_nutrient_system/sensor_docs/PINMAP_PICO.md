# 핀맵 — Raspberry Pi Pico (일반)

펌웨어: `firmware/pico/main.py`

---

## 전체 연결 요약

이 핀맵은 **일반 Raspberry Pi Pico**를 메인 MCU로 쓰는 버전이다. 여기서 통신 경로는 세 가지로 분리된다.

1. 센서 데이터 수집: `센서 RS485 -> 센서용 RS485-TTL 모듈 -> Pico GP0/GP1`
2. RP2350 터치 입력: `RP2350 내부 터치패널 -> RP2350 내부 I2C1 GP6/GP7`
3. Pico-RP2350 화면/명령 연동: `Pico GP4/GP5 -> 추가 TTL-to-RS485 모듈 -> RP2350 RS485 A/B`

따라서 RP2350 화면이 `WAIT`인 것은 3번 경로가 아직 연결되지 않았다는 뜻이다. 1번 센서 수집이 불가능하다는 뜻이 아니다.

| GPIO | 연결 대상 | 설명 |
|------|-----------|------|
| GP0  | 센서 RS485 모듈 DI | UART0 TX (Modbus 송신) |
| GP1  | 센서 RS485 모듈 RO | UART0 RX (Modbus 수신) |
| GP2  | 릴레이 모듈 IN | 릴레이 제어 |
| GP4  | TTL-to-RS485 DI | UART1 TX, RP2350으로 센서 CSV 전송 |
| GP5  | TTL-to-RS485 RO | UART1 RX, RP2350 릴레이 명령 수신 |
| GP6  | 센서 RS485 모듈 DE+RE | 수동 방향제어, 1=TX / 0=RX |
| GP16 | W5500 MISO | SPI0 RX |
| GP17 | W5500 CS   | W5500 칩셀렉 |
| GP18 | W5500 SCK  | SPI0 클럭 |
| GP19 | W5500 MOSI | SPI0 TX |
| GP20 | W5500 RST  | W5500 리셋 |
| GP25 | 온보드 LED  | 내장 LED (상태 표시) |

---

## RS485 (Modbus RTU)

이 RS485는 **센서 전용 버스**다. RP2350 LCD와 연결하는 RS485와 분리해서 생각한다.

| Pico | RS485 모듈 |
|------|-----------|
| GP0  | DI |
| GP1  | RO |
| GP6  | DE + RE |
| 5V   | VCC |
| GND  | GND |

- UART0, 9600 baud
- 센서 주소: 온습도 0x01 / 토양 0x02 / 조도 0x03 / CO2 0x04
- 센서 전원과 센서용 RS485-TTL 모듈이 살아 있으면, RP2350이 `WAIT` 상태여도 Pico는 센서 데이터를 읽을 수 있다.
- 현재 센서용 모듈은 `DI / DE / RE / RO` 수동 방향제어형이다.
- `DE+RE`는 Pico GP6에 묶어 연결한다.
- 송신 시 GP6 HIGH, `uart.flush()` 후 수신 시 GP6 LOW로 전환한다.

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

- 하드웨어 SPI0 후보 핀맵
- 현재 W5500 모듈은 과전압/전원 문제로 손상 의심 상태라, Pico 일반 버전에서는 네트워크 코드를 비활성화했다.
- 새 W5500으로 교체 후 SPI 테스트를 먼저 통과시킨 뒤 HTTP POST 코드를 다시 활성화한다.
- **주의**: W5500은 3.3V 전용이다. GND 공통을 먼저 잡고, VCC는 3.3V를 넘기지 않는다.

---

## RP2350 Touch LCD 4 (RS485 디스플레이 + 터치 릴레이)

펌웨어:

| 장치 | 펌웨어 |
|---|---|
| Pico 일반 | `firmware/pico/main.py` |
| RP2350 Touch LCD 4 | `RP2350-Touch-LCD-4/examples/hunet_pico/hunet_pico.c` |

최종 연결은 TTL UART 직결이 아니라, Pico 쪽에 TTL-to-RS485 모듈을 하나 추가해서 RP2350의 `RS485 A/B` 단자로 들어가는 방식이다.

| Pico | TTL-to-RS485 모듈 | RP2350 Touch LCD 4 |
|------|-------------------|--------------------|
| GP4 / UART1 TX | DI | - |
| GP5 / UART1 RX | RO | - |
| GND | GND | GND |
| - | A | RS485 A |
| - | B | RS485 B |

- Baudrate: 115200
- Pico → RP2350: 센서 CSV 한 줄 전송
- RP2350 → Pico: 릴레이 명령 1바이트 응답 (`0x00` OFF, `0x01` ON)
- RP2350의 터치 입력은 보드 내부 I2C1 GP6/GP7에서 처리한다.
- RP2350 뒤쪽 `SDA/SCL` I2C 커넥터도 같은 I2C1 계열이므로, Pico 일반 버전에서는 사용하지 않는다.
- RP2350 뒤쪽 `5V/3V3` 표기는 전원 핀이다. 터치 신호선으로 쓸 수 없다.
- RP2350 뒤쪽 `CAN L/H`는 CAN 차동 단자다. Pico UART나 RS485 대신 직접 사용할 수 없다.
- 현재 TTL-to-RS485 모듈이 없으므로 RP2350은 `WAIT` 상태가 정상이다.
- 임시 I2C 표시 전용 버전은 만들지 않고, 최종 RS485 구조 코드만 유지한다.
- **중요**: Pico GP4/GP5 UART를 RP2350 `RS485 A/B`에 직접 연결하면 안 된다. 반드시 TTL-to-RS485 변환 모듈을 거쳐야 한다.
- 센서용 RS485-TTL 모듈을 임시로 빌려 이 경로를 테스트했고, RP2350 화면 `LIVE` 전환 및 더미값 표시가 성공했다.
- 실제 운영에서는 센서용 RS485 모듈과 RP2350 링크용 RS485 모듈을 분리해서 사용한다.
- 재연결 중 같은 모듈이 `WAIT` 상태를 보였으나, 배선 재점검 후 다시 `LIVE` 전환에 성공했다. 모듈 불량보다 A/B, GND, TXD/RXD 재연결 오류를 먼저 의심한다.

모듈 라벨이 `DI/RO`가 아니라 `RXD/TXD`인 경우:

| Pico | RS485-TTL 모듈 |
|------|----------------|
| GP4 / UART1 TX | RXD / RX |
| GP5 / UART1 RX | TXD / TX |
| GND | GND |

### 현재 모듈 미연결 상태에서 가능한 것

| 항목 | 가능 여부 | 비고 |
|------|-----------|------|
| RP2350 대시보드 부팅 | 가능 | `hunet_pico.uf2`가 올라가 있으면 화면 표시 |
| RP2350 터치 UI 표시 | 가능 | 터치 패널 자체는 내부 I2C로 동작 |
| Pico 센서 읽기 | 가능 | 센서 전원/센서용 RS485 모듈만 있으면 됨 |
| RP2350 화면에 센서값 표시 | 불가 | Pico-RP2350 RS485 통신선이 아직 없음 |
| RP2350 터치로 Pico 릴레이 제어 | 불가 | 명령 회신 통신선이 아직 없음 |

---

## 릴레이

| Pico | 릴레이 모듈 |
|------|-----------|
| GP2 / 물리 4번핀 | IN1 / Fan |
| GP3 / 물리 5번핀 | IN2 / Pump 1 |
| GP7 / 물리 10번핀 | IN3 / Pump 2 |
| GP8 / 물리 11번핀 | IN4 / LED |
| 5V   | VCC |
| GND  | GND |

- Pico 일반 버전에서는 RP2350 터치 대시보드에서 `Fan`, `Pump 1`, `Pump 2`, `LED` 카드를 터치해 ON/OFF 명령을 보낸다.
- Pico는 UART1 RX로 받은 1바이트 릴레이 비트마스크에 따라 GP2/GP3/GP7/GP8 릴레이 출력을 제어한다.
- 현재 테스트한 4채널 릴레이 모듈은 active-low 타입이다.
  - 논리 OFF: 해당 GPIO HIGH, 릴레이 OFF
  - 논리 ON: 해당 GPIO LOW, 릴레이 ON
- 릴레이 비트마스크:
  - bit0 / `0x01`: Fan, GP2, IN1
  - bit1 / `0x02`: Pump 1, GP3, IN2
  - bit2 / `0x04`: Pump 2, GP7, IN3
  - bit3 / `0x08`: LED, GP8, IN4
- `Pump 1`과 `Pump 2`는 UI에서 터치하면 10초 동안만 ON이고, 버튼에 남은 시간이 카운트다운으로 표시된 뒤 자동 OFF된다.
- `Fan`과 `LED`는 UI에서 터치할 때마다 ON/OFF 토글된다.

4채널 확장 후보:

| Pico | 릴레이 |
|------|--------|
| GP2 / 물리 4번핀 | IN1 / Fan |
| GP3 / 물리 5번핀 | IN2 / Pump 1 |
| GP7 / 물리 10번핀 | IN3 / Pump 2 |
| GP8 / 물리 11번핀 | IN4 / LED |

부하 접점은 `NC / COM / NO` 순서였다. 팬처럼 "켰을 때만 동작"해야 하는 부하는 `COM + NO`를 쓴다.

```text
12V+ -> COM
NO -> 팬 +
팬 - -> 12V-
NC는 사용하지 않음
```

---

## 전원 구성

| 항목 | 전원 |
|------|------|
| Pico | PC USB 또는 5V |
| 센서 4종 | 12V SMPS |
| W5500 | 벅컨버터 3.3V 출력 |
| GND | SMPS / Pico / W5500 / 벅컨버터 모두 공통 |
