# 배선

Board 기준: Raspberry Pi Pico WH + Grove Shield for Pi Pico.

## 저전압 배선

| 기능 | Pico / Grove | 연결 |
|---|---|---|
| RS485 UART TX | GP0 / UART0 TX | 자동 RS485 모듈 RXD 또는 DI |
| RS485 UART RX | GP1 / UART0 RX | 자동 RS485 모듈 TXD 또는 RO |
| Fridge SSR | GP28 / A2 | XSSR 3(+) |
| Fridge SSR GND | GND | XSSR 4(-) |
| 12V LED MOSFET | GP16 / D16 | MOSFET gate |
| 12V Fan MOSFET | GP18 / D18 | MOSFET gate |
| RP2350 link TX | GP4 / UART1 TX | RP2350-link RS485 DI |
| RP2350 link RX | GP5 / UART1 RX | RP2350-link RS485 RO |
| RP2350 link DIR | GP20 / D20 | RP2350-link RS485 DE + RE |

자동 RS485 모듈은 DE/RE 핀이 없는 타입 기준이다.

```text
Grove/Pico 5V  -> RS485 VCC
Grove/Pico GND -> RS485 GND
RS485 A        -> Sensor 1 A
RS485 B        -> Sensor 1 B
```

온습도 센서 색상 기준:

```text
갈색 -> 5V
검정 -> GND
노랑 -> RS485 A
파랑 -> RS485 B
```

## 220V 배선

Grove Shield에는 220V를 절대 연결하지 않는다.

```text
갈색 L in -> XSSR 1
XSSR 2    -> 갈색 L out

파랑 N        -> 그대로 직결
초록노랑 접지 -> 그대로 직결
```

XSSR 1/2는 AC 라이브 라인만 스위칭한다. 중성선과 접지는 직결이다.  
220V 배선은 Pico/RP2350 저전압 배선과 물리적으로 분리한다.

## 12V 부하 (팬/LED)

N-channel MOSFET 로우사이드 스위칭 기준:

```text
12V + -> 부하 +
부하 - -> MOSFET drain
MOSFET source -> 12V GND
Pico/Grove GPIO -> MOSFET gate
12V GND -> Pico/Grove GND
```

팬은 가능한 경우 플라이백 다이오드 또는 보호회로가 있는 모듈을 사용한다.

## RP2350 링크 RS485

RP2350 대시보드 연결용 RS485는 센서 RS485와 분리된 별도 버스다.

Pico 쪽 수동 방향제어 RS485 모듈:

```text
Pico GP4  -> RS485 DI
Pico GP5  <- RS485 RO
Pico GP20 -> RS485 DE
Pico GP20 -> RS485 RE
Pico 5V   -> RS485 VCC
Pico GND  -> RS485 GND

RS485 A -> RP2350 RS485 A
RS485 B -> RP2350 RS485 B
```

DE와 RE는 같은 GP20에 묶는다.

RP2350 쪽 핀:

```text
UART1 TX (GP8) -> RS485 DI
UART1 RX (GP9) <- RS485 RO
Baud rate: 115200
```
