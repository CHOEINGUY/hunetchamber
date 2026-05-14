# 개발 로그

## 2026-05-07 — 하드웨어 구성 및 펌웨어 확인

### 하드웨어 맵

**Pico / RP2040:**
- SSR: GP28 → XSSR 3(+), GND → XSSR 4(-)
- 센서 RS485: GP0 TX, GP1 RX
- RP2350 링크 RS485: GP4 TX, GP5 RX, GP20 DE/RE
- MOSFET: GP16 LED, GP18 팬

**220V SSR:**
- XSSR 1/2: 컴프레셔 라이브 라인만 스위칭
- 중성선·접지: 직결
- 220V 배선과 저전압 배선 물리적 분리

### 펌웨어 확인 상태

업로드 후 `status` 응답:

```text
STATUS on=0 armed=0 auto=0 target_c=15.0 band_c=0.5 min_off_s=300 wait_on_s=0 min_on_s=300 wait_off_s=0 state_elapsed_s=311 temp_c=26.8 humidity=38.2 sensor_age_s=6 fan=0 led=0 reason=boot
```

- SSR 출력 off, armed/auto off, 기본 목표 15.0 C
- 센서 정상 (온도/습도 수신됨)
- 팬/LED 기본 0%

### RP2350 대시보드 — 응답성 개선 내용

터치 후 지연이 느껴지는 문제 발생 → 리팩토링:
- 터치 콜백에서 UART 직접 쓰기 제거
- 화면은 터치 즉시 갱신 (낙관적 업데이트)
- 명령을 큐에 넣고 메인 루프에서 전송
- 반복 터치는 최신 값으로 합산 후 1회 전송
- Pico STATUS 수신 시 보류 중인 값 덮어쓰지 않음
- wait_on_s, wait_off_s 등: Pico 기준값 수신 후 RP2350 로컬 카운팅

---

## 2026-05-08 — Raspberry Pi 게이트웨이 + Pico WH Wi-Fi 통합

### 추가 파일

```text
fridge_controller/gateway/fridge_gateway_server.py
fridge_controller/gateway/setup_fridge_db.py
fridge_controller/gateway/requirements.txt
fridge_controller/docs/05_OPERATIONS.md (RASPBERRY_PI_GATEWAY.md 통합됨)
fridge_controller/controller/pico_wh/http_post_example.py
```

### Raspberry Pi 게이트웨이

```text
Pi IP: 192.168.100.30
Port:  8081
Endpoint: POST /fridge
Dashboard: http://192.168.100.30:8081/
```

DB 테이블 생성 및 테스트 INSERT 확인 완료.

대시보드 탭:
- 실시간 상태: 최신 row + 최근 10분 미니 차트
- 데이터 분석: 기간 필터, 온도/목표/SSR 그래프 (Apache ECharts), 요약 카드, row 테이블

### Pico WH MicroPython 교체

초기 접속 시 일반 Pico MicroPython이 올라가 있었음:

```text
Raspberry Pi Pico with RP2040  ← network 모듈 없음
```

Pico W 전용 MicroPython으로 교체:

```text
MicroPython v1.27.0
Raspberry Pi Pico W with RP2040  ← network 모듈 있음
```

교체 후 `controller/pico_wh/wifi_config.py` + `controller/pico_wh/main.py` 재업로드.

### 동작 확인

Pico 시리얼:

```text
GATEWAY post_ok
```

Raspberry Pi 로그: `device fridge-01` row가 10초 간격으로 INSERT되는 것 확인.

---

## 2026-05-08 — 220V 냉장고 실 전원 연결

220V 냉장고 전원 연결 후 컨트롤러 정상 동작 확인.

테스트 시작 시점 DB 최신 row:

```text
id: 717
created_at: 2026-05-08 14:46:50 KST
temp_c: 23.2
humidity: 38.4
fridge_on: 1
armed: 1
auto_mode: 1
fan_percent: 100
led_percent: 0
target_c: 15.0
band_c: 0.5
reason: auto_hold
```

상태:
- DB 1초 주기 적재 정상
- SSR 출력 상태가 `fridge_on`으로 기록됨
- armed=1, auto=1 → 자동 제어 운전 중
- 팬 ON 상태
- 냉각 응답 및 컴프레셔 보호 동작 관찰 대기 중

---

## 2026-05-08 — 웹 대시보드 개선 및 웹 제어 기능 추가

### 대시보드 개선

- Pretendard 폰트 적용
- 데이터 분석 탭: 스무딩(원본/5초/10초), 차트 모드(온도/편차), 정상운전 시작 구간 필터
- 정상운전 시작 설정 시 차트·요약 카드·테이블 모두 해당 구간 이후 데이터만 표시
- 테이블 스크롤 고정 (max-height: 420px)
- 요약 카드: 온도 표준편차 σ, 평균 편차, SSR 사이클/시간 추가

### 웹 제어 탭 추가

웹 대시보드에서 Pico로 명령을 보내는 경로 구현.

**설계:** Pico가 이미 1초마다 Pi에 POST 하고 있는 응답에 명령을 끼워 전달.

```
웹 → POST /api/cmd → Pi (_pending_cmd 저장)
                         ↓ 다음 Pico POST 응답에 cmd 필드 포함
                      Pico → json 파싱 → handle_command() 적용
```

추가된 엔드포인트:
- `POST /api/cmd` — 명령 큐 등록 (웹 → Pi)
- `/fridge` POST 응답에 `"cmd"` 필드 추가 (Pi → Pico, 1회 전송 후 삭제)

지원 명령: `target`, `auto`, `arm`, `disarm`, `fan`, `forceoff`

**디버그 이력:**
1. Pico `json.loads(bytes)` → MicroPython은 string 필요 → `.decode()` 추가
2. `recv(512)` 한 번으로 헤더만 오고 body는 두 번째 TCP 패킷으로 분리 도착 → recv 루프로 수정 (`\r\n\r\n` + body 4 bytes 이상 확인 후 종료)

---

## 2026-05-08 — 센서 stale 처리 + 비대칭 밴드 제어

### 센서 stale NULL 처리

- `SENSOR_STALE_S = 10`: 마지막 성공 읽기로부터 10초 초과 시 `temp_c`, `humidity` → NULL로 DB 저장
- 자동 제어도 stale 상태에서 `no_temp` 홀드 (stale 값으로 제어 결정 방지)
- 차트: `connectNulls: true` 로 NULL 구간을 앞뒤 값 선형 보간 표시

---

## 2026-05-08 — 데이터 분석 및 냉각 특성 고찰 (#Analysis)

### 테스트 설정
- **목표 온도:** 15.0°C
- **히스테리시스 (Asymmetric Band):** High +0.5°C / Low -0.5°C (±0.5°C 대칭형 설정 상태에서 관찰)

### 시각화 데이터 기반 분석 결과
정상 운영 구간의 온도 추이 및 SSR 동작 로그를 분석하여 다음과 같은 특성을 확인했다.

**1. SSR ON 시점의 즉각적인 냉각 반응**
- 온도가 상한 임계값(15.5°C)에 도달하여 SSR이 켜지는 순간, 지연 없이 컴프레셔가 가동되며 온도가 즉시 하강하기 시작함.
- 시스템의 냉각 응답성이 매우 뛰어나며, 제어 명령이 물리적인 냉각 동작으로 즉각 전이됨을 확인.

**2. SSR OFF 시점의 온도 하방 관성 (Undershoot)**
- 하한 임계값(14.5°C)에 도달하여 SSR이 꺼진 후에도, 냉각 코일에 남은 냉기나 시스템의 관성으로 인해 실제 온도는 목표보다 훨씬 더 낮게 떨어지는 현상(Undershoot)이 발생함.
- 꺼진 직후에도 한동안 온도가 계속 하강하다가 반등하는 패턴을 보임.

### 제어 전략 개선 방향 (오늘의 교훈)
위 관찰 결과를 바탕으로, 원하는 '평균 온도'를 유지하기 위해 다음과 같은 비대칭 제어 전략이 유효할 것으로 판단함.

- **상방 임계값 상향 조정 (Raise Upper Target):** SSR이 켜지자마자 온도가 즉각 떨어지므로, 상한선을 현재보다 조금 더 높게 설정하여 컴프레셔 가동 빈도를 조절.
- **하방 임계값 유지 (Keep Lower Target):** 꺼진 후 발생하는 Undershoot 관성을 고려하여 하한선은 그대로 유지하거나 미세 조정하여 하한 한계점을 방어.
- **결론:** 상한 편차(`band_high_c`)를 넓히고 하한 편차(`band_low_c`)를 타이트하게 가져가는 비대칭 운용을 통해 전체적인 평균 온도를 최적화할 수 있을 것으로 기대됨.

---

### 증상

간헐적으로 `SENSOR1 err` 발생 후 센서 데이터가 수 분간 NULL로 기록됨. 팬 ON/OFF 등 다른 동작 이후 갑자기 정상 복구되는 패턴 반복.

하드웨어(진동, 접촉 불량) 문제로 의심했으나 `check_sensors.py`로 진단한 결과 **코드 버그**로 확인.

### 원인

RS485 트랜시버가 UART TX로 송신한 요청 바이트를 RX로 그대로 루프백(echo)하는 하드웨어 특성.

`read_temp_humidity()` 에서 `uart.read()` 로 받은 버퍼에 **송신 요청 8바이트 + 센서 응답 9바이트 = 17바이트**가 섞여 들어옴. CRC를 17바이트 전체로 계산하면 당연히 실패.

`check_sensors.py` 진단 출력:

```text
addr=1  raw(17)=01 03 00 00 00 02 c4 0b  01 03 04 00 8d 00 3d ...
                ← TX echo 8B →           ← 실제 응답 9B →
temp=14.1°C  humidity=61.6%  (echo 제거 후 파싱 성공)
```

센서 자체는 정상 응답 중이었으며, 소프트웨어에서 echo를 걷어내지 않아 발생한 문제.

### 수정

`read_temp_humidity()` 에 echo 감지·제거 로직 추가:

```python
resp = raw[len(req):] if len(raw) > len(req) and raw[:len(req)] == req else raw
```

수신 버퍼 앞부분이 송신 요청과 일치하면 해당 바이트를 제거한 뒤 CRC 검증 진행.

---

### 비대칭 히스테리시스 밴드 (asymmetric band)

기존 단일 `CONTROL_BAND_C` → `band_high_c` (켜기 상한 편차) / `band_low_c` (끄기 하한 편차) 분리.

- 켜기 조건: `temp >= target + band_high_c`
- 끄기 조건: `temp <= target - band_low_c`
- 웹 제어 탭에서 독립 설정 가능 (0.1°C 단위, 범위 0.1~5.0)
- 새 명령: `bandhigh <값>`, `bandlow <값>`
- DB: `band_low_c` 컬럼 추가 (`ALTER TABLE`), `band_c`는 `band_high_c` 값 유지 (하위 호환)
