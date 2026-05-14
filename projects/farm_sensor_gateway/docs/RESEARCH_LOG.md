# Hunet 연구 일지

이 문서는 개발 결과만 적는 로그가 아니라, 논의 과정에서 어떤 선택지를 검토했고 왜 채택/보류했는지 남기는 연구 일지다. 세부 구현 결과는 `docs/DEVLOG.md`, 현재 이어받기용 요약은 `docs/PROJECT_HANDOFF_LOG.md`, 실제 배선은 `docs/PINMAP_XIAO.md`와 `docs/PINMAP_PICO.md`를 함께 본다.

---

## 2026-04-23 — RS485 센서 통신 기반 구축

### 연구 질문

RP2040 계열 보드에서 RS485 Modbus RTU 센서를 안정적으로 읽고, 맥에서 데이터를 실시간으로 확인할 수 있는 최소 구조를 만들 수 있는가?

### 초기 시스템 가정

```text
RS485 sensors -> TTL/RS485 module -> RP2040 UART0 -> USB serial -> Mac monitor/dashboard
```

당시에는 W5500이나 라즈베리파이 게이트웨이까지 가지 않고, 먼저 센서가 정상 응답하는지 검증하는 것이 목표였다.

### 환경 세팅

확인/구성한 항목:

- RP2040 Zero USB 연결 확인
- Python 가상환경 `.venv` 구성
- `pyserial`, `flask`, `flask-socketio`, `mpremote` 기반 도구 준비
- `upload.py` 제작
- `mac_monitor.py` 개선
- `web_monitor.py` JS 버그 수정

의사결정:

```text
초기 펌웨어 업로드/테스트는 mpremote만 의존하지 않고 upload.py로 직접 처리한다.
```

이유:

- 현장 테스트 중 포트가 바뀌거나 REPL 상태가 꼬일 수 있음
- 간단한 스크립트 업로드를 반복해야 함
- 나중에 XIAO/Pico 일반 보드를 번갈아 쓰려면 자동 포트 탐색이 필요함

### RS485 UART 기준

최초 RS485 배선 기준:

```text
RP2040 GP0 / UART0 TX -> RS485 모듈 RX
RP2040 GP1 / UART0 RX <- RS485 모듈 TX
GND 공통
```

연구 판단:

- GP0/GP1 UART0는 센서 Modbus 전용으로 유지하는 것이 좋다.
- 이후 LCD나 다른 장치와 통신하더라도 센서 버스와 섞으면 디버깅이 어려워진다.

### 온습도 센서 검증

확인 결과:

```text
Baudrate: 9600
Slave address: 0x01
Register 0x0000: humidity
Register 0x0001: temperature
Function code: 0x03
```

판단:

- 온습도 센서는 첫 기준 센서로 삼기 좋음
- 데이터 길이가 짧고 응답이 안정적이라 RS485 버스 정상 여부 확인용으로 적합

### 토양 5-in-1 센서 1차 검증

확인 결과:

```text
Baudrate: 4800
Slave address: 0x01
Registers: moisture, soil_temp, EC, pH, N, P, K
```

문제:

- 온습도 센서와 주소가 둘 다 `0x01`
- baudrate도 온습도와 다름
- 같은 RS485 버스에 병렬 연결하려면 주소와 baudrate 통일 필요

초기 판단:

```text
토양 센서는 단독 읽기는 가능하지만, 통합 버스에 올리려면 설정 레지스터를 찾아야 한다.
```

### 1일차 결론

성공한 것:

- RP2040 UART0로 RS485 Modbus RTU 통신 가능 확인
- 온습도 센서 정상 읽기
- 토양 센서 단독 읽기
- Mac USB serial 기반 모니터링 가능성 확인

남은 문제:

- 토양 센서 주소/baud 변경
- 여러 센서 한 버스 통합
- 장기적으로 DB 저장/네트워크 전송 구조 필요

---

## 2026-04-24 — RS485 버스 통합, 조도 센서 추가, 전원 사고 기록

### 연구 질문

온습도, 토양, 조도 센서를 하나의 RS485 버스에 올리고, 동일 baudrate/서로 다른 slave address 구조로 안정적으로 통합할 수 있는가?

### 토양 센서 baudrate 변경

처음에는 잘못된 레지스터를 baud 설정 레지스터로 착각했다.

실패한 접근:

```text
0x0007을 baud 관련 레지스터로 착각하고 write 시도
```

데이터시트 확인 후 실제 레지스터:

```text
0x07D1 = baudrate 설정 레지스터
0x0000 = 2400
0x0001 = 4800
0x0002 = 9600
```

적용 명령:

```text
01 06 07 D1 00 02 59 46
```

판단:

```text
센서 설정값 변경은 데이터 레지스터와 설정 레지스터를 반드시 구분해야 한다.
데이터시트 없이 추정 write를 반복하면 센서 설정을 망가뜨릴 수 있다.
```

### 토양 센서 주소 변경

문제:

- 온습도 센서와 토양 센서가 둘 다 `0x01`
- 같은 Modbus 버스에서는 slave address 충돌 발생

확인한 레지스터:

```text
0x07D0 = Slave ID 설정 레지스터
```

적용 명령:

```text
01 06 07 D0 00 02 08 86
```

결과:

```text
온습도: 0x01
토양 5-in-1: 0x02
```

### RS485 버스 통합 판단

최종 버스 구조:

```text
RP2040 UART0 GP0/GP1
-> TTL/RS485 module
-> A/B bus
   -> 온습도 addr 0x01
   -> 토양 addr 0x02
```

판단:

- Modbus RTU에서는 한 버스에 여러 센서를 병렬로 둘 수 있음
- 각 센서는 고유 address 필요
- 모든 센서는 같은 baudrate 필요
- master는 RP2040 하나로 유지하는 것이 안정적

### 조도/일사량 센서 추가

센서:

```text
PR-300AL-RA-N01
전원: DC 7~30V, 현장에서는 12V SMPS 사용
```

설정:

```text
address: 0x03
baudrate: 9600
register 0x0000: solar W/m2
```

결과:

```text
온습도 0x01 + 토양 0x02 + 조도 0x03 통합 성공
```

### 전원 구성 결정

최종 판단:

```text
RP2040: PC USB 전원
센서 전체: 12V SMPS
GND: SMPS - 와 RP2040 GND 공통
```

이유:

- 센서 전원 요구사항이 RP2040 5V핀으로 감당하기 어려울 수 있음
- RS485 신호 기준을 맞추려면 GND 공통 필요
- 전원은 분리하되 기준 전위는 공유하는 구조가 안전함

### 하드웨어 사고와 교훈

발생한 사고:

- RP2040 Zero 1개 소손
- LM2596 벅컨버터 1개 소손

원인:

- 벅컨버터 극성 반대 연결
- 멀티미터 프로브를 잘못 꽂은 상태에서 측정

연구 교훈:

```text
전원 연결 전에는 반드시 멀티미터로 극성 확인.
빨간 리드 = +, 검정 리드 = -.
멀티미터 COM/VΩmA 단자 위치 확인.
전원 계통 변경 후에는 신호선 연결 전에 전압부터 확인.
```

### 2일차 결론

성공한 것:

- RS485 센서 3종 통합
- 주소 체계 0x01/0x02/0x03 정리
- 12V 센서 전원 + 공통 GND 구조 확립
- 웹 대시보드 항목 확장

남은 문제:

- CO2 센서 추가
- 데이터 저장 구조 결정
- 네트워크 전송 구조 검토

---

## 2026-04-29 — W5500 Ethernet 디버그와 네트워크 전송 성공

### 연구 질문

RP2040/XIAO에서 W5500 Ethernet 모듈을 사용해 센서 데이터를 맥 또는 라즈베리파이 게이트웨이로 HTTP POST 할 수 있는가?

### 초기 실패 양상

문제:

```text
W5500 SPI 응답 불안정
PHY link 안 올라옴
HTTP socket open 실패
```

초기 가설:

1. 핀맵 오류
2. SPI mode 오류
3. W5500 전원 부족
4. LAN link 문제
5. 맥과 W5500이 서로 다른 네트워크 대역

### XIAO W5500 핀맵 재확인

최종 XIAO 실제 배선:

```text
SCK  -> GP26
MOSI -> GP3
MISO -> GP4
CS   -> GP29
RST  -> GP28
```

중요한 판단:

```text
SCK=GP26, MOSI=GP3, MISO=GP4는 RP2040 하드웨어 SPI 같은 버스 조합이 아니다.
따라서 SPI(0)/SPI(1)가 아니라 SoftSPI가 필요하다.
```

최종 동작 설정:

```python
spi = SoftSPI(
    baudrate=100_000,
    polarity=1,
    phase=1,
    sck=Pin(26),
    mosi=Pin(3),
    miso=Pin(4),
)
```

### SPI mode 실험

관찰:

```text
mode 0: VERSION 0xFF
mode 1: VERSION 0xFF
mode 2/3: VERSION 0x04 확인
500kHz 이상: 응답 깨짐
```

결론:

```text
현재 USR-ES1/W5500 모듈은 100kHz, SPI mode 3에서만 안정적으로 응답한다.
```

추가 조치:

- `firmware/wiznet5k.py` 내부 SPI 재초기화가 기본 500kHz/mode0로 덮어쓰던 문제 수정
- TCP connect timeout guard 추가

### W5500 전원 문제

관찰:

```text
Pico/XIAO 3.3V핀에서 W5500 공급 시 약 2.7V 측정
```

USR-ES1 스펙:

```text
3.3V 전용
200mA 이상 필요
5V 금지
```

결론:

```text
W5500은 외부 벅컨버터 3.3V로 직접 공급해야 한다.
Pico/XIAO GND, W5500 GND, buck GND는 반드시 공통으로 묶는다.
```

### PHY link 개념 정리

논의 중 정리한 점:

- PHY link는 Wi-Fi나 IP 대역 문제가 아니라 Ethernet 물리 계층 연결 상태
- 공유기/스위치와 LAN 케이블이 전기적으로 연결되고 W5500 전원이 안정적이면 link LED가 올라와야 함
- 인터넷 연결 여부와 별개로 link 자체는 올라와야 함

### 네트워크 대역 문제

관찰:

```text
W5500 DHCP IP: 192.168.100.28
맥 IP가 처음에는 192.168.0.x 계열
```

문제:

```text
Pico/W5500이 POST하려는 대상과 맥이 서로 다른 네트워크 대역이면 직접 통신 불가
```

해결:

```text
맥 Wi-Fi를 W5500과 같은 192.168.100.x 네트워크로 변경
맥 IP: 192.168.100.29
```

결과:

```text
W5500 -> Mac 192.168.100.29:8080 HTTP POST 성공
```

### 2026-04-29 오전/오후 W5500 결론

성공한 것:

- W5500 SPI VERSION 0x04 확인
- Ethernet PHY link up
- DHCP IP 수신
- Mac HTTP server로 POST 성공

핵심 판단:

```text
W5500 문제는 단일 원인이 아니라 핀맵, SPI mode, 전원, 네트워크 대역이 동시에 얽힌 문제였다.
```

---

## 2026-04-29 — RS485 센서 4종 통합과 DB 저장 구조 전환

### 연구 질문

센서 4종 데이터를 실제 네트워크로 보내고, 웹훅 대신 MariaDB에 직접 저장하는 구조가 가능한가?

### 센서 4종 확인

`firmware/check_rs485_sensors.py`로 확인한 최종 센서 주소:

```text
0x01 온습도, FC03, reg 0x0000, count 2
0x02 토양 5-in-1, FC03, reg 0x0000, count 7
0x03 조도/solar, FC03, reg 0x0000, count 1
0x04 CO2, FC04, reg 0x0000, count 1
```

확인 결과:

```text
EXPECTED SUMMARY: ALL OK
```

샘플 값:

```text
air_temp 약 22~24C
humidity 약 34~36%
soil_temp 약 24~26C
solar 약 2~3 W/m2
co2 약 780~900 ppm
```

### 웹훅 계획에서 DB 직접 저장으로 변경

초기 계획:

```text
Pico -> Laptop gateway -> Webhook
```

부장님 요구:

```text
Webhook이 아니라 MariaDB 서버에 직접 저장
```

제공된 서버:

```text
host: 49.247.214.116
port: 3306
database/user/password: smart_chamber
```

판단:

```text
게이트웨이 서버가 HTTP POST를 받고 MariaDB INSERT를 수행하는 구조가 가장 단순하다.
Pico가 직접 DB에 접속하는 구조는 MicroPython 환경과 보안 측면에서 부적합하다.
```

### MariaDB 스키마 결정

테이블:

```text
sensor_readings
```

주요 컬럼:

```text
id, created_at, device_id,
air_temp, humidity,
moisture, soil_temp, ec, ph, n, p, k,
solar, co2, relay,
raw_json
```

판단:

- 정규 컬럼은 조회/대시보드용
- `raw_json`은 추후 필드 변경/디버깅용
- `device_id`는 여러 장치 확장 대비

### 맥 게이트웨이 구현

`gateway_server.py` 역할:

```text
POST /sensor -> JSON 수신 -> MariaDB INSERT
GET /health -> 상태 확인
GET /api/readings -> 최신 DB row 조회
GET / -> 브라우저 대시보드
```

대시보드 판단:

- DB 저장이 실제로 되는지 눈으로 확인할 필요가 있음
- 3초 자동 갱신으로 최신 row 확인
- 초기 개발 단계에서는 복잡한 프론트보다 단순 테이블/카드 UI가 충분

### 저장 주기 5초 최적화

초기 문제:

```text
DB 저장 간격이 약 9초
```

원인 분석:

```python
uart.read()
```

센서 요청 전 버퍼 비우기 용도로 사용했지만, 데이터가 없을 때 UART timeout만큼 블로킹될 수 있었다.

수정:

```python
while uart.any():
    uart.read()
```

결과:

```text
14:29:42
14:29:47
14:29:52
14:29:57
14:30:02
14:30:07
```

결론:

```text
센서 4종을 매번 읽는 구조에서 안정적으로 확인된 저장 주기는 5초.
더 줄이려면 센서별 주기 분리가 필요하다.
```

### 센서별 주기 분리 논의

판단:

```text
온습도/조도는 빠르게 읽어도 의미 있음.
CO2는 중간 주기.
토양 5-in-1은 변화가 느리므로 자주 읽을 필요가 낮음.
```

제안 구조:

```text
DB row 저장: 3초마다
온습도: 매 row 새 값
조도: 매 row 새 값
CO2: 6초마다 새 값, 나머지는 직전값 사용
토양: 15~30초마다 새 값, 나머지는 직전값 사용
```

보류 이유:

- 우선 전체 파이프라인 안정화가 더 중요
- 센서별 timestamp/신선도 표시 설계가 필요

---

## 2026-04-29 — 라즈베리파이 게이트웨이 이관

### 연구 질문

맥북이 하던 HTTP 수신/MariaDB 저장 역할을 Raspberry Pi 4 Model B로 옮길 수 있는가?

### 라즈베리파이 초기 상태

확인:

```text
Raspbian GNU/Linux 10
user: pi
hostname: raspberrypi
초기 IP: 192.168.0.178
```

문제:

```text
맥/W5500 네트워크는 192.168.100.x
라즈베리파이는 192.168.0.x
```

판단:

```text
Pico/W5500이 Pi로 POST하려면 Pi도 W5500과 같은 192.168.100.x 네트워크에 있어야 한다.
```

해결:

```text
Pi Wi-Fi/LAN을 같은 네트워크로 변경
Pi IP: 192.168.100.30
```

### 기존 OS 유지 판단

초기화 논의:

- 새로 굽는 것이 최선
- 하지만 microSD 카드 리더기가 없음
- 기존 OS에서 정리 후 게이트웨이로 사용하기로 결정

실행:

```text
apt update
python3-venv/python3-pip/git 설치
SSH 활성화
Timezone/hostname 등 정리
```

판단:

```text
현장 게이트웨이 테스트는 기존 OS로 충분하다.
나중에 카드 리더기가 생기면 Raspberry Pi OS Lite 64-bit로 새로 굽는 것이 장기적으로 좋다.
```

### SSH 키 인증과 배포 방식

목표:

```text
코드는 맥에서 수정
라즈베리파이는 배포/실행 대상
```

설정:

- 맥에서 SSH key 생성
- Pi `~/.ssh/authorized_keys`에 공개키 추가
- 이후 rsync/ssh 비밀번호 없이 진행 가능

초기 실수:

```text
rsync에서 RP2350-Touch-LCD-4/build 산출물까지 복사되어 200MB 이상 전송
```

교훈:

```text
배포용 rsync는 build, .venv, __pycache__, .git, PDF 등 제외해야 한다.
```

정리 후 배포:

```text
gateway_server.py
upload.py
firmware/
scripts/
docs/
```

### Pi 게이트웨이 동작 확인

Pi에서 수행:

```text
python3 -m venv .venv
pip install pymysql
python scripts/setup_sensor_db.py
python -u gateway_server.py
```

확인:

```text
http://192.168.100.30:8080/health OK
http://192.168.100.30:8080/api/readings OK
샘플 POST -> DB INSERT id 증가
```

### Pico POST 대상 변경

변경:

```python
SERVER_IP = '192.168.100.30'
```

결과:

```text
Pico -> W5500 -> Pi 192.168.100.30:8080/sensor -> MariaDB INSERT
```

### systemd 등록

목표:

```text
Pi 재부팅 후 gateway_server.py 자동 실행
```

서비스:

```text
/etc/systemd/system/hunet-gateway.service
After=network-online.target
Restart=always
RestartSec=5
```

검증:

```text
Pi reboot 후 hunet-gateway.service active (running)
```

### Pi 재부팅 후 Pico W5500 문제

문제:

```text
Pi 재부팅 후 Pico는 HTTP POST FAIL 반복
Pico 리셋하면 다시 OK
```

원인 추정:

```text
Pi 재부팅으로 TCP 연결/소켓 상태가 끊겼고 W5500 socket state가 꼬임.
Pico 코드가 W5500 init을 부팅 시 한 번만 수행하고, 실패 시 재초기화하지 않았음.
```

해결:

```python
fail_count += 1
if fail_count >= 3:
    nic = init_network()
    fail_count = 0
```

결론:

```text
Pi가 재부팅되어도 Pico가 3회 연속 실패 후 W5500을 재초기화하여 자동 복구 가능.
```

---

## 2026-04-29 — RP2350 Touch LCD 4 시각화 1차 완성

### 연구 질문

RP2040/XIAO가 읽은 센서 데이터를 RP2350 Touch LCD 4에 표시할 수 있는가?

### 초기 통신 후보

검토한 후보:

1. UART 직결
2. USB host 방식
3. W5500 네트워크 경유
4. I2C
5. RS485 버스 감청

초기 판단:

- USB host는 구현 복잡도가 높아 비추천
- W5500 경유는 RP2350에 네트워크가 없으므로 부적합
- 기존 센서 RS485 버스 감청은 Modbus master/slave 타이밍을 건드릴 위험이 있어 비추천
- XIAO는 노출 핀 제약 때문에 UART1 직결이 어려움

### XIAO 핀 제약 확인

XIAO RP2040 노출 핀 중 사용 중인 핀:

```text
GP0/GP1: RS485 센서 UART0
GP2: 릴레이
GP3/GP4/GP26/GP28/GP29: W5500
GP6/GP7: 비어 있음, I2C 라벨
```

판단:

```text
XIAO에서 추가 통신선으로 현실적인 선택은 GP6/GP7 I2C.
```

### RP2350 I2C 충돌 문제

처음 계획:

```text
RP2350 I2C0 GP8/GP9를 슬레이브로 사용
```

문제:

- 실제 보드에서 GP8/GP9는 외부 TTL I2C로 노출된 것이 아님
- RS485 예제는 내부 UART1 GP8/GP9를 사용
- 외부 `SDA/SCL` 커넥터는 I2C1 GP6/GP7
- I2C1은 터치/IMU와 공유

최종 1차 선택:

```text
XIAO GP6/GP7 -> RP2350 SDA/SCL
RP2350은 I2C1 슬레이브로 데이터 수신
터치 기능은 비활성화
```

이유:

- 우선 센서 데이터 표시가 1차 목표
- 터치 릴레이 제어는 후순위
- 추가 모듈 없이 바로 구현 가능

### LVGL 대시보드 구현

화면 구성:

```text
480x480 dark UI
Header: Hunet Sensor Dashboard + WAIT/LIVE
3열 x 4행 카드
Air Temp / Humidity / Solar
Moisture / Soil Temp / CO2
EC / pH / Relay
N / P / K
```

결과:

```text
RP2350 화면에 센서 데이터 표시 정상
```

연구 판단:

```text
XIAO + RP2350 조합에서는 I2C 표시 전용 방식이 가장 단순하다.
단, 터치 릴레이 제어는 I2C 충돌 때문에 다음 과제로 남긴다.
```

---

### 2026-04-30 추가 실험: 릴레이 반응 속도 개선 (Polling Decoupling)

연구 질문:

```text
센서 4개를 읽는 동안 발생하는 약 2초의 블로킹 시간 동안에도 RP2350 터치 명령을 즉시 처리할 수 있는가?
```

관찰 및 분석:

- 현재 Pico-RP2350 통신은 Pico가 센서 CSV를 보낼 때만 RP2350이 응답하는 구조임.
- 센서 읽기는 Modbus 타임아웃 때문에 한 루프에 최소 1.3~1.5초 소요됨.
- 이 기간 동안 Pico UART1 RX 버퍼에는 데이터가 쌓여도 Pico 코드가 읽지 않아 반응이 늦음.

해결 방안:

1. 전송 데이터와 제어 명령의 분리.
2. Pico가 언제든 짧게 물어볼 수 있는 `CMD?` 프로토콜 도입.
3. RP2350은 IRQ 기반으로 이 요청에 즉시 응답하도록 수정.

실행 결과:

- RP2350 C 코드 수정: `'?'` 수신 시 `g_relay_cmd` 1바이트 즉시 전송.
- Pico Python 코드 수정: `read_sensor()` 단계 사이사이에 `check_display_command()` 호출.
- 터치 반응 속도가 2초 대기에서 0.5초 이하로 체감상 즉시 반응 수준으로 개선됨.

결론:

```text
반이중(Half-Duplex) RS485 링크에서도 마스터(Pico)가 주도하는 짧은 폴링을 통해 제어 레이턴시를 획기적으로 낮출 수 있다.
```

---

## 2026-04-30 — 일반 Raspberry Pi Pico 버전 분리와 W5500 손상 이슈


### 연구 질문

기존 XIAO 버전과 별도로 일반 Raspberry Pi Pico 보드 버전을 만들 수 있는가? 일반 Pico에서는 더 안정적인 표준 SPI/I2C 핀을 사용할 수 있는가?

### 폴더 구조 분리

결정한 구조:

```text
firmware/xiao/main.py
firmware/pico/main.py
firmware/lib/
firmware/tests/
firmware/legacy/

RP2350-Touch-LCD-4/examples/hunet_xiao/
RP2350-Touch-LCD-4/examples/hunet_pico/
```

의도:

- XIAO와 일반 Pico의 핀맵을 섞지 않음
- 보드별 최적 핀을 독립적으로 선택
- 문서도 `PINMAP_XIAO.md`, `PINMAP_PICO.md`로 분리

### 일반 Pico 핀 설계

초기 제안:

```text
GP0/GP1: RS485 센서 UART0
GP2: 릴레이
GP4/GP5: RP2350 통신 후보
GP16~GP20: W5500 SPI0 후보
GP25: 온보드 LED
```

판단:

```text
일반 Pico는 XIAO보다 노출 핀이 많으므로 XIAO와 핀 번호를 맞출 필요가 없다.
보드별로 가장 안정적인 핀 조합을 선택하고 문서로 분리한다.
```

### 일반 Pico W5500 테스트

계획:

```text
GP16 MISO
GP17 CS
GP18 SCK
GP19 MOSI
GP20 RST
```

문제와 진단:

1. GND 공통 누락
   - 결과: SPI VERSION 0x00
   - 교훈: 전원 LED가 켜져도 GND 공통 없으면 SPI 통신 불가

2. GND 연결 후 VERSION 0xFF
   - 의미: MISO floating 또는 CS/MISO 응답 없음

3. Loopback 테스트
   - GP19 MOSI와 GP16 MISO 직접 연결 시 7/7 통과
   - 결론: Pico SPI 핀 자체는 정상

4. W5500 전원 문제
   - 벅 출력 약 3.0V 수준 확인
   - W5500 권장 범위보다 낮아 불안정 가능

5. 과전압/연기 발생
   - 약 3.7V 유입 추정
   - W5500 모듈에서 연기 발생
   - 이후 VERSION 0x00 반복

결론:

```text
Pico 자체는 살아있고 센서 RS485도 정상.
W5500 모듈은 손상 의심. 새 모듈 교체 전까지 일반 Pico 네트워크 코드는 비활성화.
```

### 일반 Pico 센서 테스트

W5500 제외 후 RS485 센서 4종 테스트:

```text
온습도 정상
토양 정상
조도 정상
CO2 정상
```

판단:

```text
일반 Pico 보드 자체와 RS485 센서 경로는 정상이다.
문제는 W5500 모듈 및 전원 계통에 국한된다.
```

---

## 2026-04-30 — RP2350 Touch LCD 4 통신 방식 재검토

### 연구 질문

일반 Pico와 RP2350 Touch LCD 4를 연결하면서 센서 데이터 표시뿐 아니라 터치로 릴레이 ON/OFF까지 가능하게 하려면 어떤 통신 방식이 가장 적합한가?

### 외부 단자 확인

RP2350 Touch LCD 4 외부에 보이는 단자:

```text
I2C: VCC / GND / SDA / SCL
CAN: L / H
RS485: A / B
BAT: 배터리 소켓
```

중요한 확인:

- 외부에 `GP8`, `GP9` TTL 핀이 직접 표시되어 있지 않음
- 외부 RS485 단자는 `A/B` 차동 단자
- 외부 I2C 단자는 터치/IMU와 같은 I2C1일 가능성이 높음

### I2C 방식 검토

구조:

```text
Pico GP6/GP7 또는 GP4/GP5 -> RP2350 SDA/SCL
```

장점:

- 추가 모듈 없이 가능
- 센서 표시만 목적이면 빠르게 구현 가능

문제:

- RP2350 터치 패널도 I2C를 사용
- 외부 I2C를 Pico 통신에 쓰면 터치와 충돌 가능
- 실제 XIAO 대시보드에서는 터치 비활성화로 해결

판단:

```text
I2C는 표시 전용 fallback으로 적합.
터치 릴레이까지 하려면 부적합.
```

### UART TTL 직결 방식 검토

처음 코드상 의도:

```text
Pico GP4 TX -> RP2350 GP9 RX
Pico GP5 RX <- RP2350 GP8 TX
```

문제:

```text
RP2350 보드 외부에 GP8/GP9 TTL 핀이 직접 노출되어 있지 않은 것으로 확인.
```

판단:

```text
코드는 빌드되지만 실제 배선이 가능하지 않을 수 있다.
GP8/GP9 TTL 접근 가능 여부가 확인되지 않으면 이 방식은 보류.
```

### RS485 A/B 방식 검토

가능한 구조:

```text
Pico GP4/GP5
-> TTL-to-RS485 모듈
-> RP2350 RS485 A/B
```

장점:

- RP2350의 터치 I2C를 건드리지 않음
- RP2350에서 터치 활성화 가능
- 센서 표시와 릴레이 명령 양방향 통신 가능
- 센서용 RS485 버스와 분리하면 안정적

문제:

```text
추가 TTL-to-RS485 모듈이 현재 없음
```

판단:

```text
터치 릴레이까지 안정적으로 하려면 이 방식이 가장 적합하다.
단, 모듈을 추가로 확보해야 한다.
```

### CAN L/H 방식 검토

질문:

```text
CAN L/H를 쓸 수 있는가?
```

판단:

```text
비추천.
```

이유:

- CAN은 UART가 아니다
- Pico GPIO TX/RX를 CAN L/H에 직접 연결할 수 없음
- CAN 컨트롤러/트랜시버와 CAN 프로토콜 구현 필요
- 현재 목적에 비해 복잡도 과다

### BAT 소켓 검토

질문:

```text
BAT 소켓을 통신에 쓸 수 있는가?
```

판단:

```text
절대 사용 금지.
```

이유:

- BAT는 배터리 전원용
- 신호선 연결 시 보드 손상 가능

### 2026-04-30 최종 판단

현재 추가 TTL-to-RS485 모듈이 없는 경우:

```text
최종 RS485 구조 코드는 유지
RP2350은 WAIT 상태가 정상
LCD 연동/터치 릴레이 테스트는 TTL-to-RS485 모듈 도착 전까지 보류
```

터치 릴레이까지 하려면:

```text
TTL-to-RS485 모듈 1개 추가
Pico GP4/GP5 -> TTL-to-RS485 -> RP2350 RS485 A/B
RP2350 터치 활성화 유지
```

최종 운영 판단:

```text
I2C = 추가 모듈 없이 표시만 가능하지만 임시 버전은 만들지 않음
RS485 = 모듈 필요, 표시 + 터치 릴레이에 가장 적합하므로 최종 구조로 채택
CAN = 현재 목적에 비해 과함
BAT = 전원용, 통신 사용 금지
```

### 임시 I2C 버전을 만들지 않기로 한 이유

처음에는 TTL-to-RS485 모듈이 없으므로 `Pico -> I2C -> RP2350` 표시 전용 임시 버전을 만들 수 있다고 판단했다. 하지만 이후 논의에서 임시 코드를 만들면 다음 문제가 생긴다고 정리했다.

- `hunet_pico`와 `pico/main.py`가 I2C 임시 버전과 RS485 최종 버전으로 다시 갈라짐
- 나중에 TTL-to-RS485 모듈이 오면 임시 코드를 걷어내야 함
- 터치 릴레이가 최종 목표인데, I2C 임시 버전은 터치를 포기하는 구조라 연구 목표와 어긋남
- 연구일지/핀맵/펌웨어가 더 복잡해짐

따라서 결정:

```text
임시 I2C 표시 전용 버전은 만들지 않는다.
현재 코드는 최종 RS485 구조로 유지한다.
TTL-to-RS485 모듈이 없어서 통신선이 완성되지 않은 동안 RP2350은 WAIT 상태로 둔다.
```

### 2026-04-30 추가 실험: 센서용 RS485 모듈 임시 대여

TTL-to-RS485 모듈이 별도로 오기 전이지만, 기존 센서용 RS485-TTL 모듈을 잠깐 분리해 RP2350 링크 검증에 사용할 수 있는지 실험했다.

실험 목적:

```text
Pico UART1 GP4/GP5
-> 기존 RS485-TTL 모듈
-> RP2350 RS485 A/B
```

이 경로로 센서 데이터 표시와 RP2350 응답이 실제로 가능한지 확인한다. 센서들은 이 실험 동안 연결하지 않는다.

테스트용 펌웨어:

```text
firmware/tests/test_rp2350_rs485_display.py
```

테스트 데이터:

```text
24.0,35.0,40.0,23.0,70,6.5,3,5,13,3,850,0
24.1,35.2,41.0,23.1,71,6.6,3,5,13,4,851,0
...
```

관찰 결과:

```text
RP2350 화면 WAIT -> LIVE 전환 성공
더미 센서값 표시 성공
Pico 시리얼에 `relay cmd: 0` 반복 출력
```

해석:

- Pico에서 RP2350으로 가는 RS485 표시 경로는 정상이다.
- RP2350의 CSV 파싱과 LVGL 화면 갱신은 정상이다.
- RP2350에서 Pico로 돌아오는 1바이트 응답도 정상이다.
- 따라서 최종 구조인 `Pico -> TTL-to-RS485 -> RP2350 RS485 A/B`는 실제 하드웨어에서 검증됐다.

운영 판단:

```text
임시 실험에서는 센서용 RS485 모듈을 빌려 쓸 수 있다.
실제 운영에서는 센서 RS485 버스와 RP2350 표시/명령 RS485 링크를 분리해야 한다.
따라서 TTL-to-RS485 모듈은 최종적으로 2개 필요하다.
```

### 2026-04-30 추가 실험: RP2350 터치 기반 릴레이 제어

RP2350 터치 화면의 Relay 카드를 이용해 Pico의 GPIO를 제어하고, 4채널 릴레이 모듈 IN1에 연결한 팬을 ON/OFF할 수 있는지 확인했다.

하드웨어 연결:

```text
Pico GP2 -> 4채널 릴레이 IN1
Pico GND -> 릴레이 GND
릴레이 VCC -> 릴레이 전원
```

릴레이 부하 접점:

```text
릴레이 단자 순서: NC / COM / NO
12V+ -> COM
NO -> 팬 +
팬 - -> 12V-
NC 미사용
```

처음에는 화면의 ON/OFF와 실제 릴레이 동작이 반대로 나왔다. 이는 4채널 릴레이 모듈이 active-low 입력이라는 뜻으로 해석했다. 즉 GP2가 LOW일 때 릴레이가 켜지고, HIGH일 때 꺼진다.

수정 방향:

```text
논리 상태 relay_state = 0/1로 따로 관리
relay_state 0 -> GP2 HIGH -> 릴레이 OFF
relay_state 1 -> GP2 LOW  -> 릴레이 ON
```

수정 파일:

```text
firmware/tests/test_rp2350_rs485_display.py
firmware/pico/main.py
```

결과:

```text
RP2350 터치 -> RS485 1바이트 명령 -> Pico GP2 active-low 제어 -> 릴레이/팬 ON/OFF 성공
```

### 2026-04-30 추가 실험: RP2350 링크 재연결 실패 후 복구

TTL-to-RS485 모듈을 2개로 운용하려고 재배선하는 과정에서 RP2350 화면이 다시 `WAIT` 상태로 머무는 문제가 발생했다. 같은 모듈이 앞서 더미 데이터 표시 실험에서는 정상 동작했으므로, 모듈 불량보다는 배선 조합 문제로 판단했다.

관찰:

```text
Pico는 더미 CSV를 계속 송신함
RP2350 화면은 WAIT 유지
Pico 시리얼에 relay cmd 응답도 없음
```

점검 순서:

```text
1. RP2350용 RS485 모듈 A/B 반전 확인
2. RP2350 GND와 모듈 GND 공통 확인
3. Pico GP4/GP5와 모듈 RXD/TXD 방향 확인
4. 이전에 성공했던 모듈이라는 점을 기준으로 모듈 불량 판단 보류
```

결과:

```text
배선 재조정 후 RP2350 화면 LIVE 전환 성공
모듈 자체 문제는 아니었음
재연결 시 배선 조합/GND 기준이 가장 큰 변수였음
```

운영 교훈:

- RS485 모듈 2개를 동시에 쓰면 모듈을 서로 바꾸거나 A/B 방향을 잊기 쉽다.
- 센서용 모듈과 RP2350용 모듈은 물리적으로 라벨을 붙여 구분해야 한다.
- 성공한 배선 조합은 문서에 남기고 임의로 바꾸지 않는다.
- `WAIT`가 뜨면 코드보다 먼저 RP2350 링크용 RS485 A/B, GND, RXD/TXD를 확인한다.

### 2026-04-30 추가 실험: DI/DE/RE/RO 수동 RS485 모듈 센서용 채택

추가로 가져온 RS485 모듈은 자동 방향제어형이 아니라 `DI / DE / RE / RO` 핀이 있는 수동 방향제어형이었다. 처음에는 RP2350 링크용으로 고려했으나, 센서용으로 써보기로 했다.

배선:

```text
Pico GP0 TX -> DI
Pico GP1 RX <- RO
Pico GP6 -> DE + RE
GND -> GND
A/B -> 센서 A/B
```

초기 결과:

```text
조도/CO2는 CRC OK
온습도/토양은 깨진 응답 또는 CRC 실패
```

원인:

```text
Pico가 Modbus 요청을 보낸 뒤 DE/RE를 RX 모드로 내리는 타이밍이 늦어,
빠르게 응답하는 센서의 앞부분을 놓친 것으로 판단.
```

수정:

```python
dir_pin.value(1)
uart.write(req)
uart.flush()
dir_pin.value(0)
```

결과:

```text
온습도 OK
토양 OK
조도 OK
CO2 OK
EXPECTED SUMMARY: ALL OK
```

이후 해당 방향제어 로직을 `firmware/pico/main.py`에 반영했다.

### 2026-04-30 통합 상태

현재 통합 성공 범위:

```text
센서 4종 -> 수동 RS485 모듈(DE/RE=GP6) -> Pico
Pico -> RP2350 RS485 링크 -> LCD 화면 표시
RP2350 터치 -> RS485 응답 -> Pico -> active-low 릴레이/팬 제어
```

W5500은 뜨거워지는 문제가 있어서 분리했다. `main.py`는 W5500 초기화 실패 시 예외를 잡아 네트워크만 비활성화하고 나머지 센서/RP2350/릴레이 루프는 계속 실행하도록 했다.

남은 UX 문제:

```text
릴레이 터치 반응이 즉시 반영되지 않는다.
현재는 Pico가 센서값을 RP2350에 보낼 때 RP2350이 릴레이 상태 1바이트를 응답하는 구조라,
터치 명령 반영이 센서 루프 주기에 묶인다.
```

개선 방향:

```text
센서값 전송: 3~5초마다
릴레이 명령 poll: 0.3~0.5초마다

Pico -> RP2350: CMD?
RP2350 -> Pico: 0x00 또는 0x01
```

---

## 현재 연구상 남은 질문

1. 릴레이 명령 반응속도 개선을 위해 RP2350 `CMD?` poll 프로토콜을 추가할지 결정해야 한다.
2. 릴레이 터치 명령은 단순 1바이트로 동작 확인됐지만, 최종 운영에서 CRC/프레임을 추가할지 결정해야 한다.
3. W5500 모듈 발열 원인을 해결해야 한다. 해결 전까지 연결하지 않는다.
4. 최종 제품에서는 XIAO 버전을 유지할지 일반 Pico 버전으로 전환할지 결정해야 한다.
