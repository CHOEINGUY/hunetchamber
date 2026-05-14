# Gateway database plan

작성일: 2026-04-29

## 목표

센서 데이터를 Pico / W5500 Ethernet을 통해 노트북으로 보내고, 노트북이 받은 데이터를 MariaDB에 저장한다.

최종적으로는 노트북의 역할을 Raspberry Pi로 대체한다.

## 전체 구조

현재 목표 구조:

```text
RS485 센서들
-> Pico / Seeed XIAO RP2040
-> W5500 Ethernet
-> 노트북 HTTP 수신 서버
-> MariaDB INSERT
```

최종 목표 구조:

```text
RS485 센서들
-> Pico / Seeed XIAO RP2040
-> W5500 Ethernet
-> Raspberry Pi HTTP 수신 서버
-> MariaDB INSERT
```

## 진행 순서

지금은 웹훅부터 붙이지 않는다.

먼저 Pico에서 실제 센서 데이터를 HTTP POST로 쏘고, 노트북이 안정적으로 받는지 확인한다.

이 순서가 맞는 이유:

1. W5500 네트워크 연결은 이제 성공했지만, 실제 센서 루프와 함께 오래 돌려본 상태는 아니다.
2. 센서 데이터 파싱, 빈 값, 일부 센서 응답 실패 같은 문제가 먼저 드러날 수 있다.
3. 웹훅을 먼저 붙이면 문제가 Pico 쪽인지, 노트북 서버 쪽인지, 외부 웹훅 쪽인지 구분하기 어려워진다.
4. 노트북 수신 로그가 안정화된 뒤 웹훅 전달을 붙이면 Raspberry Pi로 옮길 때도 구조가 단순하다.

따라서 현재 우선순위:

```text
1. Pico -> 노트북 수신 안정화
2. MariaDB 테이블 생성
3. 노트북 -> MariaDB 저장 추가
4. Raspberry Pi로 게이트웨이 역할 이전
```

## 현재 DB 저장 성공 상태

MariaDB 서버 접속 확인 완료.

```text
host=49.247.214.116
port=3306
database=smart_chamber
user=smart_chamber
version=10.6.4-MariaDB
```

생성한 테이블:

```text
sensor_readings
```

현재 노트북 게이트웨이 서버:

```text
gateway_server.py
POST /sensor
0.0.0.0:8080
```

최종 확인 결과:

```text
Pico -> gateway_server.py -> MariaDB INSERT 성공
```

최근 DB 행 예시:

```text
device_id=pico-w5500-01
air_temp=23.70
humidity=33.80
moisture=0.00
soil_temp=25.20
solar=3
co2=832
relay=0
```

## 1단계: Pico -> 노트북 수신 안정화

목표:

Pico가 RS485 센서 데이터를 읽고, W5500 Ethernet으로 노트북 HTTP 서버에 JSON POST를 보낸다.

현재 사용 예정 파일:

| 역할 | 파일 |
|------|------|
| Pico 통합 펌웨어 | `firmware/rp2040_main.py` |
| 노트북 수신 서버 | `test_http_server.py` |
| W5500 단독 POST 테스트 | `firmware/test_http_post.py` |
| W5500 디버그 문서 | `docs/W5500_DEBUG_STATUS.md` |
| W5500 핀맵 문서 | `docs/PINMAP_W5500.md` |

노트북 수신 서버 실행:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 test_http_server.py
```

Pico에 통합 펌웨어 업로드:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 upload.py firmware/rp2040_main.py
```

판정 기준:

- 노트북 터미널에 `/sensor` POST가 반복 수신된다.
- JSON에 실제 센서 필드가 포함된다.
- 일부 센서가 응답하지 않아도 서버가 죽지 않는다.
- 최소 몇 분 이상 반복 전송된다.
- 맥 IP가 바뀌었을 때 `SERVER_IP`만 바꾸면 다시 동작한다.

예상 JSON 필드:

```json
{
  "humidity": 55.1,
  "air_temp": 25.3,
  "moisture": 0.0,
  "soil_temp": 27.2,
  "ec": 0,
  "ph": 9.0,
  "n": 0,
  "p": 0,
  "k": 0,
  "solar": 123,
  "co2": 412,
  "relay": 0
}
```

## 2단계: 노트북 내부 처리

노트북이 받은 데이터를 그대로 웹훅으로 넘기기 전에, 수신 데이터를 안정적으로 다룰 수 있게 한다.

추가할 수 있는 기능:

- 수신 시각 `timestamp` 추가
- 원본 JSON 터미널 출력
- JSON Lines 로그 파일 저장
- 필수 필드 누락 검사
- 센서별 null 허용 정책 정리
- 최근 수신 시간 표시

추천 로그 형식:

```json
{"timestamp":"2026-04-29T13:52:00+09:00","air_temp":25.3,"humidity":55.1,"co2":412}
```

## 3단계: 노트북 -> MariaDB 저장

노트북 수신 서버가 안정화되면, 받은 데이터를 MariaDB에 저장한다.

구조:

```text
Pico POST /sensor
-> 노트북 수신
-> JSON 파싱
-> MariaDB sensor_readings INSERT
-> INSERT id 로그 출력
```

정해야 할 것:

- DB 접속 정보는 환경변수로 덮어쓸 수 있게 유지
- 원본 JSON은 `raw_json` 컬럼에 함께 저장
- 실패 시 HTTP 500 응답
- 나중에 장기 운영 시 재시도 큐 또는 로컬 파일 백업 검토

초기에는 단순하게 간다:

```text
받기 성공
-> DB INSERT 1회
-> 성공/실패 로그 출력
```

## 4단계: Raspberry Pi로 이전

노트북에서 검증된 Python 서버를 Raspberry Pi로 옮긴다.

Raspberry Pi 역할:

- 고정 IP 또는 DHCP 예약 IP 사용
- Pico/W5500의 POST 수신
- 로그 저장
- MariaDB 저장
- 부팅 시 자동 실행

이전 시 바뀌는 것:

| 항목 | 노트북 단계 | Raspberry Pi 단계 |
|------|-------------|-------------------|
| 수신 서버 | `test_http_server.py` 또는 확장 서버 | 동일 Python 서버 |
| IP | 맥 Wi-Fi IP | Pi IP |
| 실행 방식 | 터미널 수동 실행 | systemd 자동 실행 |
| 로그 | 터미널 / 파일 | 파일 / systemd journal |
| DB 저장 | 노트북에서 INSERT | Pi에서 INSERT |

Pico 코드에서 바뀔 값:

```python
SERVER_IP = "라즈베리파이_IP"
SERVER_PORT = 8080
SERVER_PATH = "/sensor"
```

## 현재 결론

지금 당장 해야 하는 것은 웹훅 구현이 아니라, `firmware/rp2040_main.py`를 보드에 올려서 실제 센서 데이터가 노트북으로 안정적으로 들어오는지 확인하는 것이다.

현재는 `gateway_server.py`로 DB 저장까지 성공했다.

다음은 이 서버를 계속 켜두고 장시간 수집 안정성을 확인한다.
