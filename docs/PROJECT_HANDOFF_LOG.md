# Hunet project handoff log

작성일: 2026-04-29

이 문서는 나중에 다시 이어서 작업할 때 현재 상태를 바로 파악하기 위한 정리본이다.

## 한 줄 요약

Seeed XIAO RP2040 / Pico Zero가 RS485 센서 4종을 읽고, USR-ES1(W5500) Ethernet으로 맥 게이트웨이에 HTTP POST를 보낸다. 맥은 데이터를 MariaDB `sensor_readings` 테이블에 저장하고, 브라우저 대시보드로 최신 데이터를 보여준다.

현재 동작 확인 완료:

```text
RS485 sensors -> Pico -> W5500 Ethernet -> Mac gateway -> MariaDB
```

## 현재 성공 상태

| 항목 | 상태 |
|---|---|
| W5500 SPI 인식 | 성공 |
| Ethernet PHY link | 성공 |
| W5500 DHCP | 성공 |
| RS485 센서 4종 응답 | 성공 |
| Pico HTTP POST | 성공 |
| 맥 게이트웨이 수신 | 성공 |
| MariaDB 접속/테이블 생성 | 성공 |
| DB INSERT | 성공 |
| 웹 대시보드 표시 | 성공 |
| DB 저장 주기 | 5초 확인 |

## 하드웨어

### 보드/모듈

- MCU: Seeed XIAO RP2040 / Pico Zero 계열
- Ethernet: USR-ES1 Serial to Ethernet Module, W5500 기반
- Sensor bus: RS485 Modbus RTU
- Gateway PC: MacBook, 현재 IP `192.168.100.29`
- Database: MariaDB 서버 `49.247.214.116:3306`

### W5500 전원

USR-ES1/W5500은 3.3V 전용이다. 5V를 넣으면 안 된다.

Pico 3.3V 핀으로 W5500에 전원을 공급했을 때 멀티미터상 약 2.7V까지 떨어졌다. W5500은 최소 200mA 이상 안정적인 3.3V가 필요하므로, 현재는 벅 컨버터를 3.3V로 세팅해서 W5500에 직접 공급한다.

전원 기준:

| 연결 | 설명 |
|---|---|
| Buck 3.3V OUT | W5500 VCC |
| Buck GND | W5500 GND |
| Pico GND | W5500/Buck GND와 공통 |

W5500의 GND 핀이 여러 개 있어도 구별해서 특정 GND를 써야 하는 것은 아니다. 같은 GND net이므로 하나 이상을 공통 접지에 연결하면 된다. 안정성을 위해 GND는 확실하게 공통으로 묶는다.

### W5500 핀맵

현재 실제 배선 기준이다.

| W5500 / USR-ES1 | Pico GPIO | MicroPython |
|---|---:|---|
| SCK | GP26 | `sck=Pin(26)` |
| MO / MOSI | GP3 | `mosi=Pin(3)` |
| MI / MISO | GP4 | `miso=Pin(4)` |
| CS | GP29 | `cs=Pin(29)` |
| RST | GP28 | `rst=Pin(28)` |
| VCC | 외부 3.3V | - |
| GND | 공통 GND | - |

중요:

```text
SCK=GP26, MOSI=GP3, MISO=GP4
```

이 조합은 RP2040 하드웨어 SPI의 같은 버스 핀 조합이 아니다. 따라서 `SPI(0)` 또는 `SPI(1)`가 아니라 `SoftSPI`를 사용한다.

현재 동작하는 SPI 설정:

```python
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

확인된 내용:

- mode 0에서는 W5500 VERSION이 `0xFF`로 읽혔다.
- mode 3, 100kHz에서는 VERSION `0x04` 확인.
- 500kHz 이상에서는 응답이 깨졌다.
- 현재는 `baudrate=100_000`, `polarity=1`, `phase=1` 유지.

### RS485 센서 핀맵

| 항목 | 연결 |
|---|---|
| RS485 UART TX | GP0 |
| RS485 UART RX | GP1 |
| Baudrate | 9600 |
| GND | 공통 GND |

현재 통합 코드:

```python
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), timeout=600)
```

## 센서 주소와 파싱

현재 센서 확인 결과:

| 센서 | 주소 | Function | Register | Count | 데이터 |
|---|---:|---:|---:|---:|---|
| 온습도 | `0x01` | `0x03` | `0x0000` | 2 | humidity, air_temp |
| 토양 5-in-1 | `0x02` | `0x03` | `0x0000` | 7 | moisture, soil_temp, ec, ph, n, p, k |
| 조도/solar | `0x03` | `0x03` | `0x0000` | 1 | solar |
| CO2 | `0x04` | `0x04` | `0x0000` | 1 | co2 |

`firmware/check_rs485_sensors.py`로 전체 센서 확인 완료:

```text
temp_humidity addr=0x01 OK
soil_5in1 addr=0x02 OK
solar addr=0x03 OK
co2 addr=0x04 OK
EXPECTED SUMMARY: ALL OK
```

샘플 측정값:

```text
temp=22.7C humidity=35.6%
soil moisture=0.0% temp=24.6C ec=0 ph=5.7 n=0 p=0 k=0
solar=3 W/m2
co2=787 ppm
```

## 네트워크

현재 성공 당시 네트워크:

| 항목 | 값 |
|---|---|
| Mac IP | `192.168.100.29` |
| W5500 DHCP IP | `192.168.100.28` |
| Gateway | `192.168.100.1` |
| HTTP target | `http://192.168.100.29:8080/sensor` |

주의:

- 맥 Wi-Fi가 바뀌면 맥 IP가 바뀔 수 있다.
- 그 경우 `firmware/rp2040_main.py`의 `SERVER_IP`를 새 맥 IP로 바꿔서 다시 업로드해야 한다.
- W5500 PHY link는 노트북 Wi-Fi와 별개다. LAN 케이블이 공유기/스위치와 전기적으로 연결되고 W5500 전원이 정상일 때 link LED가 올라와야 한다.

## 데이터 흐름

현재 구조:

```text
Pico main.py
  1. RS485 센서 순차 읽기
  2. JSON 생성
  3. W5500 TCP 연결
  4. POST /sensor

Mac gateway_server.py
  1. POST /sensor 수신
  2. JSON 파싱
  3. MariaDB sensor_readings INSERT
  4. GET / 로 대시보드 제공
  5. GET /api/readings 로 최신 데이터 조회
```

## MariaDB

서버 정보:

```text
host=49.247.214.116
port=3306
database=smart_chamber
user=smart_chamber
```

현재 테이블:

```text
sensor_readings
```

컬럼:

```text
id
created_at
device_id
air_temp
humidity
moisture
soil_temp
ec
ph
n
p
k
solar
co2
relay
raw_json
```

테이블 생성 스크립트:

```text
scripts/setup_sensor_db.py
```

게이트웨이 서버:

```text
gateway_server.py
```

## 현재 실행/접속 방법

### 맥 게이트웨이 서버 실행

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 -u gateway_server.py
```

성공 시 출력:

```text
Hunet gateway server
HTTP: 0.0.0.0:8080
DB: 49.247.214.116:3306/smart_chamber user=smart_chamber
Endpoint: POST /sensor
Dashboard: http://127.0.0.1:8080/
```

### 대시보드

맥에서 보기:

```text
http://127.0.0.1:8080/
```

같은 LAN의 다른 기기에서 보기:

```text
http://192.168.100.29:8080/
```

API:

```text
http://127.0.0.1:8080/api/readings?limit=30
```

### Pico 포트 확인

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 -m serial.tools.list_ports -v
```

현재 확인된 포트 예:

```text
/dev/cu.usbmodem101
```

### RS485 센서 전체 확인

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/mpremote connect /dev/cu.usbmodem101 run firmware/check_rs485_sensors.py
```

### W5500 POST 테스트

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/mpremote connect /dev/cu.usbmodem101 run firmware/test_http_post.py
```

### 통합 펌웨어 업로드

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 upload.py firmware/rp2040_main.py
```

이 명령은 `firmware/rp2040_main.py`를 보드의 `main.py`로 업로드하고 보드를 리셋한다.

### DB 테이블 생성/확인

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 scripts/setup_sensor_db.py
```

### 최신 DB row 확인

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 - <<'PY'
import pymysql

conn = pymysql.connect(
    host='49.247.214.116',
    port=3306,
    user='smart_chamber',
    password='smart_chamber',
    database='smart_chamber',
    charset='utf8mb4',
)
try:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM sensor_readings')
        print('count=', cur.fetchone()[0])
        cur.execute('''
            SELECT id, created_at, device_id, air_temp, humidity,
                   moisture, soil_temp, solar, co2, relay
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT 5
        ''')
        for row in cur.fetchall():
            print(row)
finally:
    conn.close()
PY
```

## 현재 주기

현재 `firmware/rp2040_main.py`는 모든 센서를 매번 읽고 DB에 5초 간격으로 저장되는 것까지 확인했다.

검증된 DB timestamp:

```text
14:29:42
14:29:47
14:29:52
14:29:57
14:30:02
14:30:07
```

5초로 줄인 핵심 수정:

```python
def read_sensor(req, wait_ms=300):
    while uart.any():
        uart.read()
    uart.write(req)
    time.sleep_ms(wait_ms)
    return uart.read() if uart.any() else None
```

기존 `uart.read()` 직접 호출은 데이터가 없을 때 UART timeout만큼 블로킹될 수 있었다. 이 때문에 저장 간격이 약 9초까지 늘어났다.

현재 센서 대기값:

| 센서 | wait |
|---|---:|
| 온습도 | 250ms |
| 토양 | 350ms |
| 조도 | 250ms |
| CO2 | 450ms |
| 센서 사이 대기 | 50ms |
| 루프 마지막 대기 | 500ms |

## 더 빠른 주기에 대한 판단

전체 센서를 매번 읽는 구조에서는 5초가 현재 안정 확인된 값이다.

더 줄이려면 센서별 주기를 나누는 편이 맞다.

추천안:

| 센서 | 추천 읽기 주기 | 이유 |
|---|---:|---|
| 온습도 | 2~3초 | 공기 변화 추적용 |
| 조도 | 2~3초 | 빛 변화 추적용 |
| CO2 | 5~6초 | 급격히 변하지 않음 |
| 토양 5-in-1 | 15~30초 | 토양 수분/EC/pH/NPK는 느리게 변함 |

가능한 다음 구조:

```text
DB row 저장: 3초마다
온습도/조도: 매 row 새로 읽기
CO2: 6초마다 새로 읽고 나머지는 직전값 재사용
토양: 15초마다 새로 읽고 나머지는 직전값 재사용
```

이렇게 하면 DB는 3초마다 쌓이면서 RS485 버스 부담은 줄일 수 있다.

## 주요 파일

| 파일 | 역할 |
|---|---|
| `firmware/rp2040_main.py` | 현재 보드에 올라가는 통합 펌웨어 |
| `firmware/check_rs485_sensors.py` | RS485 센서 4종 확인 |
| `firmware/test_http_post.py` | W5500 HTTP POST 단독 테스트 |
| `firmware/probe_w5500_spi.py` | W5500 SPI 모드/속도 프로브 |
| `firmware/wiznet5k.py` | W5500 드라이버, 현재 SPI 설정 패치됨 |
| `firmware/wiznet5k_socket.py` | W5500 socket 호환 레이어 |
| `gateway_server.py` | 맥 게이트웨이, DB 저장, 대시보드 |
| `scripts/setup_sensor_db.py` | MariaDB 테이블 생성 |
| `docs/PINMAP_W5500.md` | W5500 핀맵 |
| `docs/W5500_DEBUG_STATUS.md` | W5500 디버그 기록 |
| `docs/DEVLOG.md` | 누적 개발 로그 |
| `docs/PROJECT_HANDOFF_LOG.md` | 현재 정리 문서 |

## 현재 떠 있는 서비스 확인

8080 서버 확인:

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

현재 서버를 재시작하려면:

```bash
pid=$(lsof -tiTCP:8080 -sTCP:LISTEN || true)
if [ -n "$pid" ]; then kill $pid; fi
cd /Users/choeingyumac/Hunet
.venv/bin/python3 -u gateway_server.py
```

## 다음 작업 후보

1. 센서별 읽기 주기 분리
   - 목표: DB 3초 저장, 토양/CO2는 느린 주기
2. DB 접속정보를 코드 기본값이 아니라 `.env` 또는 실행 환경변수로 분리
3. 맥 IP 변경 대응
   - `SERVER_IP`를 한 곳에서 관리하거나 DHCP 예약/고정 IP 사용
4. 라즈베리파이로 게이트웨이 이관
   - `gateway_server.py` 실행
   - Python venv 구성
   - systemd 서비스 등록
   - 라즈베리파이 IP로 Pico `SERVER_IP` 변경 후 업로드
5. 대시보드 개선
   - 센서별 그래프
   - 기간 필터
   - CSV 다운로드
6. DB 스키마 확장
   - 장치 위치
   - 센서 상태/CRC 실패 카운트
   - 읽기 성공 여부
   - 센서별 timestamp

## 주의사항

- W5500에 5V 금지.
- Pico GND, W5500 GND, 벅 GND는 반드시 공통.
- 현재 W5500 SPI는 `SoftSPI`여야 한다.
- `SCK=26`, `MOSI=3`, `MISO=4`, `CS=29`, `RST=28`을 바꾸면 코드도 같이 바꿔야 한다.
- 맥 IP가 바뀌면 Pico는 기존 IP로 POST하므로 저장이 끊긴다.
- 대시보드가 보인다고 Pico가 살아있는 것은 아니다. 최신 row 시간이 계속 증가하는지 확인해야 한다.
- DB row가 늘면 `Pico -> Mac -> MariaDB` 흐름 전체가 성공한 것이다.
