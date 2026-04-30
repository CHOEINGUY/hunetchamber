# W5500 debug status

작성일: 2026-04-28

## 현재 목표

Seeed XIAO RP2040 / Pico Zero에서 W5500 이더넷 모듈을 통해 맥(`192.168.100.29:8080`)으로 HTTP POST를 보내는 것.

맥 수신 서버는 `test_http_server.py`이며 `0.0.0.0:8080`에서 POST를 받는다.

## 현재 실제 배선

현재 배선은 하드웨어 SPI의 고정 핀 조합이 아니므로 `SoftSPI`를 사용한다.

| W5500 | GPIO | 설정 |
|-------|------|------|
| SCK | GP26 | `sck=Pin(26)` |
| MOSI / MO | GP3 | `mosi=Pin(3)` |
| MISO / MI | GP4 | `miso=Pin(4)` |
| CS | GP29 | `cs=Pin(29)` |
| RST | GP28 | `rst=Pin(28)` |
| VCC | 외부 3.3V | 벅 컨버터 3.3V 출력 |
| GND | 공통 GND | Pico GND와 벅 컨버터 GND 공통 |

현재 코드 설정:

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

## 현재 전원 구성

USR-ES1 스펙상 입력 전원은 3.3V이며, 동작 전류는 200mA 이상 필요하다.

Pico의 3.3V 핀에서 W5500에 전원을 공급했을 때 멀티미터로 약 2.7V가 측정되었다. 이 전압은 W5500 PHY 링크가 뜨지 않는 원인이 될 수 있다.

현재는 벅 컨버터를 3.3V로 세팅하여 W5500에 직접 공급하는 방향으로 변경했다.

주의:

- USR-ES1에는 5V를 넣지 않는다.
- 벅 컨버터 출력은 W5500 VCC에 연결한다.
- 벅 컨버터 GND, W5500 GND, Pico GND는 반드시 공통으로 묶는다.
- 전원 투입 후 W5500 VCC-GND에서 3.25V~3.35V 근처가 나오는지 확인한다.

## 확인된 사실

처음에는 `SPI(0)` 또는 `SPI(1)` 하드웨어 SPI로 시도했지만, 현재 배선 조합에서는 맞지 않았다.

`SCK=GP26`, `MOSI=GP3`, `MISO=GP4`는 RP2040 하드웨어 SPI의 같은 버스 핀 조합이 아니므로 `SoftSPI`가 필요하다.

`polarity=0`, `phase=0`에서는 W5500 VERSION 레지스터가 `0xFF`로 읽혔다.

`polarity=1`, `phase=1`, `baudrate=100_000`에서는 W5500 VERSION 레지스터가 `0x04`로 읽혔다. 따라서 W5500 칩 자체는 SPI에서 인식된다.

`baudrate=500_000` 이상에서는 SPI 응답이 깨졌다.

## 프로브 결과 요약

`firmware/probe_w5500_spi.py`로 확인했다.

| 설정 | 결과 |
|------|------|
| SoftSPI SCK=26 MOSI=3 MISO=4, mode 0 | `VERSION=0xFF` |
| SoftSPI SCK=26 MOSI=3 MISO=4, mode 1 | `VERSION=0xFF` |
| SoftSPI SCK=26 MOSI=3 MISO=4, mode 2 | `VERSION=0x04` 확인 |
| SoftSPI SCK=26 MOSI=3 MISO=4, mode 3 | `VERSION=0x04` 확인 |
| SoftSPI SCK=26 MOSI=3 MISO=4, mode 3, 500kHz | 응답 깨짐 |
| SoftSPI SCK=26 MOSI=3 MISO=4, mode 3, 1MHz | 응답 깨짐 |
| MOSI/MISO 반대 조합 | 정상 응답 없음 |

현재 코드에서는 mode 3, `100_000` baudrate를 사용한다.

## 수정한 파일

- `docs/PINMAP_W5500.md`
  - 실제 배선 기준으로 재작성.
  - `SoftSPI`, `SCK=26`, `MOSI=3`, `MISO=4`, `CS=29`, `RST=28` 명시.

- `firmware/wiznet5k.py`
  - 드라이버 내부 SPI 재초기화 설정을 `baudrate=100000`, `polarity=1`, `phase=1`로 변경.
  - 이유: 드라이버가 내부에서 SPI를 다시 `500kHz mode 0`으로 덮어써서 초기화가 실패했음.

- `firmware/test_http_post.py`
  - 실제 배선 기준 `SoftSPI` 테스트 코드로 변경.
  - 맥 `192.168.100.29:8080`으로 테스트 POST 전송 시도.

- `firmware/rp2040_main.py`
  - `network` 모듈 방식 제거.
  - 보드에 `network` 모듈이 없어 커스텀 `wiznet5k.py` 드라이버 방식으로 변경.
  - 실제 배선 기준 `SoftSPI` 적용.

- `firmware/test_w5500.py`
  - 실제 배선 기준 `SoftSPI` 적용.

- `firmware/test_phy_modes.py`
  - 실제 배선 기준 `SoftSPI` 적용.

- `firmware/probe_w5500_spi.py`
  - W5500 VERSION 레지스터와 SPI 모드/속도 확인용 프로브 추가.

- `upload.py`
  - `/dev/cu.usbmodem101` 고정 제거.
  - 현재 연결된 RP2040 포트를 자동 탐색하도록 변경.

## 현재 테스트 결과

초기 실패 시 `firmware/test_http_post.py` 실행 결과:

```text
W5500 초기화...
IP 설정 완료: 192.168.0.80
PHY 재설정 중...
  1초: PHYCFGR=0x00 LNK=0
  ...
  10초: PHYCFGR=0x00 LNK=0
HTTP POST 전송 중... 192.168.0.30:8080
오류: Could not open socket in TCP or UDP mode.
```

이후 맥을 W5500과 같은 네트워크로 재연결하여 맥 IP가 `192.168.100.29`로 변경되었다. HTTP POST 대상도 `192.168.100.29:8080`으로 변경했다.

최종 성공 결과:

```text
W5500 초기화...
DHCP 설정 완료
IFCONFIG: (bytearray(b'\xc0\xa8d\x1c'), bytearray(b'\xff\xff\xff\x00'), bytearray(b'\xc0\xa8d\x01'), (168, 126, 63, 1))
PHY 재설정 중...
  1초: PHYCFGR=0xFF LNK=1
링크 UP
HTTP POST 전송 중... 192.168.100.29:8080
응답: b'HTTP/1.0 200 OK...'
전송 완료
```

## 현재 상태

W5500 칩은 SPI에서 인식된다.

Ethernet PHY 링크도 올라온다.

DHCP로 `192.168.100.28`을 받았고, 맥 `192.168.100.29:8080`으로 HTTP POST 전송에 성공했다.

## 다음 확인 항목

1. `firmware/rp2040_main.py`를 보드 `main.py`로 업로드한다.
2. 센서 데이터 수집 루프와 HTTP POST가 함께 동작하는지 확인한다.
3. 맥 IP가 바뀌면 `SERVER_IP` / `SERVER` 값을 새 IP로 갱신한다.

## 테스트 명령

맥 수신 서버:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 test_http_server.py
```

W5500 SPI 프로브:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/mpremote connect /dev/cu.usbmodem1101 run firmware/probe_w5500_spi.py
```

HTTP POST 테스트:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/mpremote connect /dev/cu.usbmodem1101 run firmware/test_http_post.py
```

테스트 코드를 보드의 `main.py`로 업로드:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 upload.py firmware/test_http_post.py
```
