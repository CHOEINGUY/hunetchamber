# Hunet 개발 로그

현재 상태를 한 번에 파악하려면 먼저 `docs/PROJECT_HANDOFF_LOG.md`를 본다.
논의 과정과 의사결정 흐름은 `docs/RESEARCH_LOG.md`에 따로 정리한다.

---

### 릴레이 UI 명칭 변경 및 Pump 1/2 10초 타이머 추가

RP2350 하단 릴레이 UI를 실제 액추에이터 이름 기준으로 정리했다.

```text
Relay 1 -> Fan
Relay 2 -> Pump 1
Relay 3 -> Pump 2
Relay 4 -> LED
```

Pico 릴레이 출력도 1바이트 비트마스크 방식으로 확장했다.

```text
bit0 / 0x01 -> Fan    -> Pico GP2 / relay IN1
bit1 / 0x02 -> Pump 1 -> Pico GP3 / relay IN2
bit2 / 0x04 -> Pump 2 -> Pico GP7 / relay IN3
bit3 / 0x08 -> LED    -> Pico GP8 / relay IN4
```

Fan과 LED는 기존처럼 터치할 때마다 ON/OFF 토글된다. Pump 1과 Pump 2는 터치하면 10초 동안 ON 상태가 되고, UI 버튼 값에 남은 시간이 `10s`, `9s`처럼 카운트다운으로 표시된다. 시간이 끝나면 RP2350이 해당 명령 비트를 자동으로 OFF로 바꾸고, Pico는 다음 `?` poll 응답에서 이를 받아 릴레이를 끈다.

수정 파일:

```text
RP2350-Touch-LCD-4/examples/hunet_pico/hunet_pico.c
firmware/pico/main.py
docs/PINMAP_PICO.md
```

검증:

```text
python3 -m py_compile firmware/pico/main.py
make hunet_pico -j8
```

결과:

```text
[100%] Built target hunet_pico
```

---

### 대시보드 UI/UX 대규모 개편 — 4채널 확장 대비 및 듀얼 테마 도입

대시보드의 시각적 완성도와 사용성을 높이기 위해 UI를 전면 재설계했다.

**1. 레이아웃 재구성 (3x4 그리드 + 푸터)**:
- **메인 그리드**: 11개의 센서 카드와 1개의 시스템 상태 카드로 3x4 레이아웃 구성.
- **릴레이 푸터**: 최하단에 별도의 4열 영역을 만들어 릴레이 제어 버튼을 배치. 향후 4채널 확장을 위한 자리를 미리 확보함.
- **상태 통합**: 헤더의 `LIVE/WAIT` 표시를 삭제하고, 12번째 카드인 **[Pico Status]**에서 동적으로 연결 상태(`WAITING...` -> `CONNECTED`)를 표시하도록 통합.

**2. 듀얼 테마 (Dark/Light) 모드 도입**:
- 헤더 우측에 **설정(톱니바퀴) 버튼** 추가.
- 터치 시 **다크 모드(Slate Dark)**와 **라이트 모드(Soft White)**가 실시간 토글됨.
- 각 테마에 맞는 색상 팔레트(배경, 카드, 텍스트) 적용으로 가독성 및 심미성 향상.

**3. 기술적 개선**:
- 지원되지 않는 폰트(Montserrat 18/10) 에러 수정 ( Montserrat 16/12 사용).
- 테마 전환 시 UI 객체를 초기화하고 재구성하는 엔진 구조 구현.

**결과**: 상용 제품 수준의 깔끔한 대시보드 UI 완성. 릴레이 제어와 센서 확인이 직관적으로 분리됨.

---

### 최종 배포 — Pico & RP2350 통합 펌웨어 업데이트 완료


Pico와 RP2350 양측의 펌웨어를 모두 업데이트하여 개선된 릴레이 제어 시스템을 최종 배포했다.

- **Pico**: `firmware/pico/main.py` 업로드 완료. 센서 루프 중 `'?'` 폴링 수행.
- **RP2350**: `hunet_pico.uf2` 플래싱 완료. `'?'` 요청에 IRQ 기반 즉각 응답.

**최종 동작 확인 결과**:
- 센서 데이터(온습도, 토양, 조도, CO2) 화면 표시 정상 복구.
- 터치 릴레이 반응 속도가 2초 지연에서 **즉각 반응(0.5초 이내)** 수준으로 개선됨을 확인.
- 전체 시스템 안정성 및 통신 무결성 검증 완료.

---

### 후속 개선 — 릴레이 터치 반응 속도 향상 (Decoupling)


기존에는 Pico가 센서 4개를 다 읽은 후(약 2초)에만 RP2350으로 데이터를 보내고 릴레이 명령을 받아왔기 때문에, 터치 후 반응이 최대 2초까지 지연되었다. 이를 해결하기 위해 폴링 구조를 개선했다.

개선 내용:

1. **RP2350 디스플레이 (C)**:
   - UART RX IRQ 핸들러에 `'?'` 단일 바이트 폴링 요청 처리 추가
   - `'?'` 수신 시 현재 릴레이 상태(`g_relay_cmd`)를 즉시 응답

2. **Pico 펌웨어 (Python)**:
   - `check_display_command()` 함수 구현: `'?'`를 보내고 응답을 받아 릴레이 제어
   - 메인 루프 내 센서 읽기 사이사이에 `check_display_command()`를 배치
   - 결과적으로 터치 반응 속도가 0.3~0.5초 이내로 대폭 향상됨

수정 파일:

- `RP2350-Touch-LCD-4/examples/hunet_pico/hunet_pico.c`
- `firmware/pico/main.py`

결과:

- 센서 읽기 중에도 실시간에 가까운 릴레이 제어 가능 확인
- 전체 루프 주기는 유지하면서 제어 레이턴시만 선택적 축소

---

## 2026-05-08 (냉장고 컨트롤러 통합 및 실전 테스트)

### 완료된 작업
- **Raspberry Pi 게이트웨이 연동:** `8081` 포트 기반 데이터 적재 서버 구축 및 DB 자동화 완료.
- **Pico WH Wi-Fi 통합:** 일반 Pico에서 Wi-Fi 지원 버전으로 교체 및 안정적인 HTTP POST 통신 구현.
- **웹 대시보드 및 제어 인터페이스:** 실시간 데이터 시각화(Apache ECharts) 및 웹→Pi→Pico 명령 전달 경로(Command Queue) 완성.
- **냉장고 실전 전원 연결:** 220V 컴프레셔 연동 후 실제 냉각 사이클 동작 확인.

### 주요 이슈 해결 및 고찰
- **RS485 Echo 버그:** 하드웨어 루프백으로 인한 CRC 오류 수정 (Echo 제거 로직 적용).
- **데이터 분석 (#Analysis):** 냉각 시 즉각적인 반응과 정지 후의 온도 하방 관성(Undershoot) 확인. 상한선을 높여 평균 온도를 조절하는 비대칭 제어 전략 도출.

---


### 후속 확인 — WAIT 상태와 통신 경로 분리

RP2350에 `hunet_pico.uf2`를 올리고 Pico에 `firmware/pico/main.py`를 업로드했다. 현재 TTL-to-RS485 모듈이 없으므로 RP2350 화면은 `WAIT` 상태가 정상이다. 이 `WAIT`는 Pico가 센서를 못 읽는다는 뜻이 아니라, Pico에서 RP2350으로 가는 표시/명령용 RS485 경로가 아직 없다는 뜻이다.

현재 통신 경로는 다음 세 가지로 분리해서 관리한다.

```text
1. 센서 데이터 수집
   RS485 센서들 -> 센서용 RS485-TTL 모듈 -> Pico UART0 GP0/GP1

2. RP2350 터치 입력
   RP2350 터치 패널 -> RP2350 내부 I2C1 GP6/GP7

3. Pico-RP2350 화면/명령 연동
   Pico UART1 GP4/GP5 -> 추가 TTL-to-RS485 모듈 -> RP2350 RS485 A/B
```

따라서 TTL-to-RS485 모듈이 오기 전까지 가능한 것과 불가능한 것을 다음처럼 정리했다.

| 항목 | 현재 가능 여부 | 설명 |
|---|---|---|
| RP2350 대시보드 부팅 | 가능 | `hunet_pico.uf2`가 정상 플래시됨 |
| RP2350 터치 UI 표시 | 가능 | 터치는 RP2350 내부 I2C로 동작 |
| Pico 센서 읽기 | 가능 | 센서 전원/센서용 RS485 모듈이 연결되면 독립적으로 동작 |
| RP2350 화면 센서값 표시 | 불가 | Pico-RP2350 RS485 통신선이 아직 없음 |
| RP2350 터치로 Pico 릴레이 제어 | 불가 | 명령 회신 경로가 아직 없음 |

정리된 핀맵은 `docs/PINMAP_PICO.md`에 반영했다. `RP2350` 뒤쪽 `SDA/SCL`은 터치와 같은 I2C 계열이라 Pico 일반 버전에서는 사용하지 않는다. `5V/3V3`은 전원 핀이고, `CAN L/H`는 CAN 차동 단자이므로 UART/RS485 대체 신호선으로 쓰지 않는다.

### 후속 검증 — 센서용 RS485 모듈 임시 대여로 RP2350 링크 성공

추가 TTL-to-RS485 모듈이 아직 없어서, 센서 버스에 쓰던 RS485-TTL 모듈을 잠깐 분리해 Pico-RP2350 링크 검증에 사용했다. 센서들은 이 테스트 중 연결하지 않았다.

임시 테스트 배선:

```text
Pico GP4 / UART1 TX -> RS485-TTL 모듈 RXD 또는 DI
Pico GP5 / UART1 RX <- RS485-TTL 모듈 TXD 또는 RO
Pico GND            -> RS485-TTL 모듈 GND

RS485-TTL 모듈 A -> RP2350 RS485 A
RS485-TTL 모듈 B -> RP2350 RS485 B
RS485-TTL 모듈 GND -> RP2350 GND
```

테스트 펌웨어:

```text
firmware/tests/test_rp2350_rs485_display.py
```

테스트 결과:

```text
Pico -> RP2350 더미 센서 CSV 전송 성공
RP2350 화면 WAIT -> LIVE 전환 확인
RP2350 화면에 24.x / 35.x / 40.x / CO2 850대 더미값 표시 성공
RP2350 -> Pico 릴레이 명령 1바이트 응답 확인: relay cmd: 0
```

이 검증으로 다음이 확인됐다.

| 항목 | 결과 |
|---|---|
| Pico UART1 GP4/GP5 송수신 | 정상 |
| RP2350 RS485 A/B 수신 | 정상 |
| RP2350 화면 CSV 파싱/갱신 | 정상 |
| RP2350에서 Pico로 1바이트 응답 | 정상 |
| 최종 구조 타당성 | 확인 완료 |

주의: 이 테스트는 기존 센서용 RS485 모듈을 임시로 빌려 쓴 것이므로, 실제 운영에서는 센서용 모듈과 RP2350 링크용 모듈을 분리해서 2개 사용한다.

### 후속 재검증 — RP2350 RS485 링크 재연결 성공

RS485 모듈을 2개로 나눠 재배선하는 과정에서 RP2350이 다시 `WAIT` 상태로 머물렀다. 처음에는 모듈 불량을 의심했지만, 해당 모듈은 앞서 RP2350 더미 데이터 테스트에 성공했던 모듈이었다. 최종적으로 문제는 모듈 자체가 아니라 재연결 시 A/B, GND, TX/RX 조합이 달라진 데 있었다.

확인 내용:

```text
Pico는 test_rp2350_rs485_display.py로 더미 CSV를 계속 송신
RP2350 화면은 WAIT 상태
배선 재점검 후 RP2350 화면 LIVE 전환 성공
```

정리:

```text
RP2350 링크용 모듈은 불량이 아니었다.
재연결 시에는 GND 공통과 A/B 방향을 반드시 먼저 확인한다.
Pico GP4/GP5와 모듈 RXD/TXD 연결도 모듈 라벨 기준으로 다시 확인한다.
성공한 조합은 그대로 고정하고, 센서용 모듈과 서로 바꾸지 않는다.
```

### 후속 검증 — RP2350 터치로 4채널 릴레이 IN1 ON/OFF 성공

RP2350 터치 대시보드의 Relay 카드를 눌러 Pico GP2에 연결된 4채널 릴레이 모듈의 IN1을 제어했다. 릴레이 접점은 `NC / COM / NO` 순서였고, 팬은 `COM + NO` 조합으로 연결했다.

제어 배선:

```text
Pico GP2 / 물리 4번핀 -> 4채널 릴레이 IN1 또는 Signal
Pico GND              -> 릴레이 GND
릴레이 VCC            -> 릴레이 모듈 전원
```

부하 배선:

```text
12V+ -> 릴레이 COM
릴레이 NO -> 팬 +
팬 - -> 12V-
NC는 사용하지 않음
```

테스트 중 릴레이 동작이 화면 ON/OFF와 반대로 나와서 active-low 타입으로 판단했다. 이에 따라 Pico 코드에서 논리 명령과 실제 GP2 출력값을 분리했다.

```text
Relay OFF 명령: relay cmd 0 -> GP2 pin 1 -> 릴레이 OFF
Relay ON  명령: relay cmd 1 -> GP2 pin 0 -> 릴레이 ON
```

수정한 파일:

```text
firmware/tests/test_rp2350_rs485_display.py
firmware/pico/main.py
```

결과:

```text
RP2350 터치 -> RS485 응답 -> Pico GP2 -> 릴레이 IN1 -> 팬 ON/OFF 성공
```

### 후속 통합 — 수동 DE/RE 센서 모듈 + RP2350 + 릴레이 동시 동작

추가로 구한 RS485 모듈은 `DI / DE / RE / RO` 핀이 있는 수동 방향제어형이었다. 이 모듈을 센서용으로 사용하기로 하고, Pico GP6으로 `DE+RE`를 묶어 제어했다.

센서용 수동 RS485 모듈 배선:

```text
Pico GP0 / UART0 TX -> 모듈 DI
Pico GP1 / UART0 RX <- 모듈 RO
Pico GP6            -> 모듈 DE + RE
Pico GND            -> 모듈 GND
모듈 A/B            -> 센서 RS485 A/B
```

처음에는 온습도/토양 응답 CRC가 깨졌으나, 송신 후 바로 수신 모드로 전환하는 타이밍을 `uart.flush()` 기반으로 고치자 정상화됐다.

핵심 코드:

```python
sensor_dir.value(1)  # TX
uart.write(req)
uart.flush()
sensor_dir.value(0)  # RX
```

검증 결과:

```text
온습도 OK: temp=24.8C humidity=34.9%
토양 OK: moisture=0.0% soil_temp=26.xC ph=7.5
조도 OK: solar=3 W/m2
CO2 OK: co2=925ppm 전후
RP2350 표시/응답 OK: Display relay cmd 0/1 수신
릴레이 active-low 제어 OK
```

현재 통합 펌웨어:

```text
firmware/pico/main.py
```

현재 제한:

```text
W5500은 뜨거워지는 문제가 있어 분리 상태다.
main.py는 W5500 초기화 실패 시 네트워크만 비활성화하고 센서/RP2350/릴레이 루프는 계속 돌도록 방어 처리했다.
릴레이 터치 반응은 현재 센서 송신 주기에 묶여 있어 즉시 반영되지 않는다.
다음 개선은 센서값 전송 주기와 릴레이 명령 poll 주기를 분리하는 것이다.
```

### 현재 목표

기존 Seeed XIAO RP2040 버전은 유지하고, Raspberry Pi Pico 일반 보드용 펌웨어와 RP2350 Touch LCD 4용 화면을 별도 구조로 분리한다.

### 폴더 구조

```text
firmware/
  xiao/main.py       # Seeed XIAO RP2040 버전
  pico/main.py       # Raspberry Pi Pico 일반 버전
  lib/               # W5500 공용 라이브러리
  tests/             # 테스트 스크립트
  legacy/            # 예전 개별 센서 스크립트

RP2350-Touch-LCD-4/examples/
  hunet_xiao/        # XIAO 시절 대시보드, I2C 수신/터치 비활성
  hunet_pico/        # Pico 일반용 대시보드, UART 수신/터치 릴레이
```

### Pico 일반 버전 통신 방식

처음에는 Pico GP4/GP5를 I2C0으로 쓰려 했지만, RP2350 Touch LCD 4의 뒤쪽 `SDA/SCL` 커넥터는 I2C1 GP6/GP7이고 터치 패널도 같은 버스를 사용한다. 터치를 살리려면 센서 데이터 수신을 I2C1에서 분리해야 한다.

최종 코드 방향:

```text
Pico GP4 / UART1 TX -> TTL-to-RS485 DI -> RP2350 RS485 A/B
Pico GP5 / UART1 RX <- TTL-to-RS485 RO <- RP2350 RS485 A/B
GND 공통
Baudrate 115200
```

동작:

```text
Pico -> RP2350: air_temp,humidity,moisture,soil_temp,ec,ph,n,p,k,solar,co2,relay\n
RP2350 -> Pico: 릴레이 명령 1바이트 (0x00 OFF, 0x01 ON)
```

### 완료된 코드 상태

- `firmware/pico/main.py`
  - RS485 센서 4종 읽기 유지
  - RP2350 통신을 I2C에서 UART1 GP4/GP5 기반 RS485 전송 구조로 변경
  - RP2350에서 받은 1바이트 명령으로 GP2 릴레이 제어
  - W5500은 현재 손상 의심 상태라 네트워크 코드 비활성화

- `RP2350-Touch-LCD-4/examples/hunet_pico/hunet_pico.c`
  - 온보드 RS485 포트 뒤의 UART1 GP8/GP9로 Pico 센서 CSV 수신
  - I2C1 GP6/GP7은 터치 패널용으로 유지
  - Relay 카드를 터치하면 `g_relay_cmd` 토글
  - 다음 센서 CSV 수신 시 현재 릴레이 명령을 Pico로 1바이트 응답

### 빌드 확인

```text
cd /Users/choeingyumac/Hunet/RP2350-Touch-LCD-4/build
make hunet_pico -j8
```

결과:

```text
[100%] Built target hunet_pico
```

UF2:

```text
RP2350-Touch-LCD-4/build/examples/hunet_pico/hunet_pico.uf2
```

### 배선

자세한 핀맵:

```text
docs/PINMAP_PICO.md
docs/PINMAP_XIAO.md
```

Pico 일반 + RP2350 최종 배선:

```text
Pico GP4 -> TTL-to-RS485 DI
Pico GP5 <- TTL-to-RS485 RO
TTL-to-RS485 A -> RP2350 RS485 A
TTL-to-RS485 B -> RP2350 RS485 B
GND 공통
```

주의:

```text
RP2350 외부 단자는 RS485 A/B 차동 단자다.
Pico UART GP4/GP5를 A/B에 직접 연결하면 안 된다.
TTL-to-RS485 모듈이 올 때까지 RP2350은 WAIT 상태가 정상이다.
임시 I2C 표시 전용 버전은 만들지 않고 최종 RS485 코드만 유지한다.
```

### W5500 상태

일반 Pico 테스트 중 W5500 전원 문제로 모듈 손상 의심 상태가 됐다. Pico 자체는 살아있고 RS485 센서 4종 응답은 정상 확인했다.

새 W5500으로 교체하기 전까지 일반 Pico 버전은:

```text
RS485 sensors -> Pico -> UART -> RP2350 LCD
```

표시/릴레이 제어만 우선 테스트한다.

---

## 2026-04-29 (저녁 — RP2350 Touch LCD 4 대시보드 완성)

### 완료된 작업

#### RP2350 Touch LCD 4 LVGL 대시보드 구현 ✅
- `examples/hunet_dashboard/hunet_dashboard.c` 신규 작성
- `examples/hunet_dashboard/CMakeLists.txt` 신규 작성
- `examples/CMakeLists.txt`에 `add_subdirectory(hunet_dashboard)` 한 줄 추가

#### I2C 통신 핀 문제 해결 ✅
- 최초 계획: I2C0 GP8/GP9 슬레이브 → RS485 커넥터 뒤에 트랜시버 칩 있어서 직접 접근 불가
- 보드의 "SDA/SCL" 레이블 커넥터 = I2C1 GP6/GP7 (터치·IMU 전용)
- **해결**: 슬레이브를 I2C1(GP6/GP7)로 변경, `bsp_i2c_init()` / `lv_port_indev_init()` 제거 (터치 비활성화)
- 터치는 대시보드에서 불필요하므로 trade-off 수용

#### 최종 통신 구조
- XIAO RP2040: SoftI2C 마스터 GP6(SDA)/GP7(SCL), 주소 0x42
- RP2350 Touch LCD 4: I2C1 슬레이브 GP6(SDA)/GP7(SCL), 주소 0x42
- CSV 포맷: `air_temp,humidity,moisture,soil_temp,ec,ph,n,p,k,solar,co2,relay\n`
- 배선: XIAO GP6→RP2350 SDA, XIAO GP7→RP2350 SCL, GND 공통

#### LVGL 화면 구성
- 480×480 다크 테마 (배경 #0f172a)
- 헤더: "Hunet Sensor Dashboard" + WAIT/LIVE 상태 표시
- 3열 4행 카드 그리드 (총 12개 센서값)
  - 행0: Air Temp / Humidity / Solar
  - 행1: Moisture / Soil Temp / CO2
  - 행2: EC / pH / Relay
  - 행3: N / P / K
- 데이터 수신 시 WAIT → LIVE (녹색) 전환

#### 빌드 및 플래시
- `cmake .. && make hunet_dashboard -j8` 성공
- `hunet_dashboard.uf2` BOOTSEL 방식으로 RP2350 플래시 완료
- 실제 동작 확인: 센서 데이터 화면 표시 정상

#### 향후 과제 (미완료)
- RP2350 터치로 릴레이 ON/OFF 제어 (현재 터치 비활성 상태, I2C 충돌 문제)
  - 해결 방향: 데이터 수신을 I2C0(GP12/GP13)으로 옮기면 I2C1 터치 복구 가능

---

## 2026-04-29 (오후 — 전체 파이프라인 완성 + Pi systemd 등록)

### 완료된 작업

#### RP2350 Touch LCD 4 빌드 환경 세팅 ✅
- cmake 설치 (brew)
- ARM GNU 툴체인 설치 (gcc-arm-embedded cask) — 심볼릭링크 오류 발생했지만 실제 바이너리는 정상 설치됨
  - 경로: `/Applications/ArmGNUToolchain/15.2.rel1/arm-none-eabi/bin/`
- Pico SDK v2.x 클론: `~/pico-sdk` (서브모듈 포함)
- `~/.zshrc`에 PATH, PICO_SDK_PATH 영구 등록
- `cmake .. && make -j8` 성공 → `.uf2` 18종 빌드 완료

#### 전체 센서 파이프라인 동작 확인 ✅
- `firmware/check_rs485_sensors.py`로 센서 4종 응답 전부 확인
  - 0x01 온습도 OK / 0x02 토양 OK / 0x03 조도 OK / 0x04 CO2 OK
- `firmware/rp2040_main.py` → 보드 `main.py`로 업로드
- W5500 DHCP + PHY 링크 정상
- Pico → W5500 → Pi `192.168.100.30:8080/sensor` HTTP POST → MariaDB INSERT 5초 주기 확인

#### 라즈베리파이 게이트웨이 systemd 등록 ✅
- `/etc/systemd/system/hunet-gateway.service` 생성
- `After=network-online.target` — 네트워크 올라온 후 시작
- `Restart=always`, `RestartSec=5` — 크래시 시 자동 재시작
- `systemctl enable hunet-gateway` — 부팅 자동 실행 등록
- **Pi 재부팅 후 자동 기동 확인 완료** (재부팅 테스트 통과)
- 로그: `/home/pi/Hunet/gateway_server.log`

### 현재 최종 상태

| 항목 | 값 |
|---|---|
| Pico SERVER_IP | 192.168.100.30 (Pi) |
| Pi gateway | systemd `hunet-gateway.service`, active (running) |
| DB 저장 주기 | 약 5초 |
| 대시보드 | http://192.168.100.30:8080/ |
| MariaDB | 49.247.214.116:3306 / smart_chamber / sensor_readings |

#### W5500 자동 재연결 로직 추가 ✅
- 문제: Pi 재부팅 시 Pico W5500 소켓이 꼬여서 `HTTP POST: FAIL` 반복 → 수동 리셋 필요했음
- 해결: `fail_count` 카운터 추가, 3회 연속 실패 시 `init_network()` 재호출로 W5500 재초기화
- 이제 Pi 재부팅돼도 Pico가 약 15~20초 내 자동 복구
- `firmware/rp2040_main.py` 수정 후 보드 업로드 완료

### 다음 할 일
- 센서별 읽기 주기 분리 (온습도/조도 빠르게, 토양/CO2 느리게)
- RP2350 Touch LCD 4 시각화 개발 (UART1 직결 방식 유력)
- Pi OS 교체 (SD카드 리더기 생기면 Lite 64-bit 새로 굽기)

---

## 2026-04-29 (W5500 Ethernet 디버그)

### 목표

Seeed XIAO RP2040 / Pico Zero에서 USR-ES1(W5500) Ethernet 모듈을 사용해 맥의 HTTP 수신 서버(`test_http_server.py`)로 센서 JSON을 POST하는 것.

### 최종 성공 상태

W5500 테스트 POST 성공.

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

| 항목 | 값 |
|---|---|
| 맥 IP | `192.168.100.29` |
| W5500 DHCP IP | `192.168.100.28` |
| Gateway | `192.168.100.1` |
| HTTP server | `test_http_server.py`, `0.0.0.0:8080` |
| POST target | `192.168.100.29:8080/sensor` |

### 현재 W5500 배선

현재 배선은 RP2040 하드웨어 SPI 고정 핀 조합이 아니므로 `SoftSPI`를 사용한다.

| USR-ES1 / W5500 | Pico GPIO | 설명 |
|---|---:|---|
| SCK | GP26 | `sck=Pin(26)` |
| MO / MOSI | GP3 | `mosi=Pin(3)` |
| MI / MISO | GP4 | `miso=Pin(4)` |
| CS | GP29 | `cs=Pin(29)` |
| RST | GP28 | `rst=Pin(28)` |
| VCC | 외부 3.3V | 벅 컨버터 3.3V 출력 |
| GND | 공통 GND | Pico GND / 벅 GND / W5500 GND 공통 |

최종 MicroPython 설정:

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

### 삽질 및 원인 정리

1. 처음에는 XIAO 기본 SPI 핀 기준으로 `SCK=GP2`, `MOSI=GP3`, `MISO=GP4`를 의심했으나 실제 배선은 `SCK=GP26`, `MOSI=GP3`, `MISO=GP4`였다.
2. 이 조합은 하드웨어 `SPI(0)`/`SPI(1)`로 묶이는 핀셋이 아니므로 `SoftSPI`가 필요했다.
3. `polarity=0`, `phase=0`에서는 W5500 VERSION 레지스터가 `0xFF`로 읽혔다.
4. `polarity=1`, `phase=1`, `baudrate=100_000`에서 VERSION 레지스터 `0x04` 확인.
5. `baudrate=500_000` 이상에서는 응답이 깨졌다. 현재는 `100_000` 유지.
6. Pico 3.3V 핀에서 W5500 전원을 공급했을 때 실제 전압이 약 2.7V로 떨어졌다.
7. USR-ES1 스펙상 3.3V 전용, 200mA 이상 필요. 5V 금지.
8. 벅 컨버터를 3.3V로 세팅해 W5500에 직접 공급하고, GND를 공통으로 묶은 뒤 PHY 링크가 올라왔다.
9. 맥이 처음에는 `192.168.0.30`, W5500은 DHCP로 `192.168.100.28`을 받아 서로 다른 네트워크였다.
10. 맥 Wi-Fi를 W5500과 같은 네트워크로 바꾸어 `192.168.100.29`가 된 뒤 HTTP POST 성공.

### 코드 변경

- `docs/PINMAP_W5500.md`
  - 실제 배선, 외부 3.3V 전원, `SoftSPI` 설정 정리.
- `docs/W5500_DEBUG_STATUS.md`
  - W5500 디버그 전체 경과와 성공 로그 기록.
- `firmware/wiznet5k.py`
  - 드라이버 내부 SPI 재초기화가 mode 0 / 500kHz로 덮어쓰던 문제 수정.
  - 현재 `baudrate=100000`, `polarity=1`, `phase=1`.
  - TCP connect timeout 보호 로직 추가.
- `firmware/test_http_post.py`
  - DHCP 사용.
  - 서버 IP `192.168.100.29`.
  - `s.settimeout(2)` 추가. 응답이 256바이트보다 짧을 때 무한 대기 방지.
- `firmware/rp2040_main.py`
  - `network` 모듈 방식 제거.
  - 커스텀 `wiznet5k.py` + `wiznet5k_socket.py` 방식으로 W5500 사용.
  - DHCP 사용 및 서버 IP `192.168.100.29`.
- `firmware/probe_w5500_spi.py`
  - SPI 모드/속도별 W5500 VERSION 레지스터 프로브 추가.
- `upload.py`
  - 고정 포트 `/dev/cu.usbmodem101` 제거.
  - 현재 연결된 RP2040 포트 자동 탐색.

### 재현 절차

맥 수신 서버 실행:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 test_http_server.py
```

현재 맥 IP 확인:

```bash
ifconfig en0
route -n get default
```

W5500 테스트 POST:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/mpremote connect /dev/cu.usbmodem101 run firmware/test_http_post.py
```

포트가 다르면 `/dev/cu.usbmodem101` 대신 현재 포트를 사용한다. 확인 명령:

```bash
.venv/bin/python3 -m serial.tools.list_ports -v
```

W5500 SPI 프로브:

```bash
.venv/bin/mpremote connect /dev/cu.usbmodem101 run firmware/probe_w5500_spi.py
```

### 다음 작업

1. 노트북 수신 서버에 로그 저장 기능을 추가한다.
2. 노트북 수신 서버에서 웹훅 전달 기능을 추가한다.
3. 맥 IP가 바뀌면 `firmware/rp2040_main.py`의 `SERVER_IP`와 `firmware/test_http_post.py`의 `SERVER`를 새 IP로 갱신한다.
4. 가능하면 나중에 서버 IP를 설정 파일/상수 문서로 분리한다.

### 추가 확인: 센서 통합 POST 성공

`firmware/check_rs485_sensors.py`로 RS485 센서 4종 응답 확인 완료.

```text
temp_humidity addr=0x01 OK
soil_5in1 addr=0x02 OK
solar addr=0x03 OK
co2 addr=0x04 OK
EXPECTED SUMMARY: ALL OK
```

`firmware/rp2040_main.py`를 실행하여 센서 수집 + W5500 HTTP POST 통합 흐름 확인 완료.

```text
=== Hunet 통합 센서 시작 ===
W5500 초기화...
PHYCFGR=0xFF LNK=1
링크 UP
DHCP 설정 완료: 192.168.100.28
{'co2': 817, 'solar': 3, 'humidity': 34.3, 'air_temp': 23.3, ...}
HTTP POST: OK
```

수정된 `firmware/rp2040_main.py`를 보드 `main.py`로 업로드 완료.

### 추가 확인: MariaDB 저장 성공

부장님이 제공한 MariaDB 서버 접속 확인 완료.

```text
host=49.247.214.116
port=3306
user=smart_chamber
password=smart_chamber
database=smart_chamber
version=10.6.4-MariaDB
```

생성한 테이블:

```text
sensor_readings
```

추가한 파일:

- `scripts/setup_sensor_db.py`: `sensor_readings` 테이블 생성 스크립트
- `gateway_server.py`: 맥에서 `POST /sensor` 수신 후 MariaDB에 저장하는 게이트웨이 서버

### 추가 확인: 실시간 조회 화면 추가

`gateway_server.py`에 DB 조회 API와 브라우저 대시보드를 추가했다.

```text
Dashboard: http://127.0.0.1:8080/
LAN access: http://192.168.100.29:8080/
API:       http://127.0.0.1:8080/api/readings?limit=30
```

동작 상태:

```text
Pico -> W5500 -> Mac gateway -> MariaDB INSERT 성공
대시보드가 MariaDB 최신 row를 3초마다 자동 갱신
sensor_readings 최신 row 확인 완료
```

현재 보드 업로드 상태:

```text
firmware/rp2040_main.py -> Pico main.py 업로드 완료
SERVER_IP = 192.168.100.29
HTTP_TIMEOUT_SECONDS = 2
```

### 추가 확인: 저장 주기 5초로 조정

초기 통합 코드에서는 DB 저장 간격이 약 9초였다. 원인은 센서 요청 전에 `uart.read()`로 버퍼를 비우는 과정이 데이터가 없을 때 UART timeout만큼 블로킹될 수 있었기 때문이다.

수정 내용:

```text
uart.read() 직접 호출 -> while uart.any(): uart.read() 로 non-blocking flush
센서별 wait_ms 단축
루프 마지막 대기 500ms
```

검증 결과:

```text
sensor_readings latest rows:
14:29:42
14:29:47
14:29:52
14:29:57
14:30:02
14:30:07

결과: 5초 간격 저장 확인
```
- `gateway_server.py`: Pico/W5500 POST 수신 후 MariaDB INSERT

현재 동작 구조:

```text
Pico / W5500
-> POST http://192.168.100.29:8080/sensor
-> gateway_server.py
-> MariaDB sensor_readings INSERT
```

DB 저장 확인:

```text
count=5
latest device_id=pico-w5500-01
air_temp=23.70
humidity=33.80
solar=3
co2=832
```

실행 명령:

```bash
cd /Users/choeingyumac/Hunet
.venv/bin/python3 -u gateway_server.py
```

---

## 2026-04-24 (2일차)

### 완료된 작업

#### 조도(일사량) 센서 연결 ✅ (3번째 센서)
- 모델: PR-300AL-RA-N01 (전원 DC 7~30V → 12V SMPS 사용)
- 설정 레지스터 토양센서와 동일 (0x07D1 baud, 0x07D0 addr)
- baud 4800 → 9600, addr 0x01 → 0x03 변경 완료
- 데이터 레지스터: 0x0000 → 일사량 (W/m²)
- 전용 펌웨어: `firmware/rp2040_solar.py`
- 통합 펌웨어 및 웹 대시보드 Solar 카드 추가

#### 3개 센서 통합 완료 ✅
- 온습도(0x01) + 토양(0x02) + 조도(0x03) 동일 RS485 버스
- 출력 포맷: `AirTemp:X | Humidity:X% || Moisture:X% | SoilTemp:X | EC:X | pH:X | N:X P:X K:X || Solar:X W/m2`
- 웹 대시보드 전체 항목(10개) 실시간 표시 확인

#### 전원 구성 최종 결정
- RP2040: PC USB 전원
- 센서 전체: 12V SMPS → 각 센서 VCC 직결
- GND: SMPS `-` ↔ RP2040 GND 공통 연결

#### 하드웨어 사고 및 교훈
- RP2040 Zero 1개 소손 (벅컨버터 극성 반대 연결)
- LM2596 벅컨버터 1개 소손 (멀티미터 프로브 잘못 꽂고 측정)
- **교훈: 전원 연결 전 반드시 멀티미터로 극성 확인. 빨간=+, 검정=-. COM/VΩmA 단자 확인**
- 새 보드로 교체 후 정상 복구

---

### 다음 할 일 (2026-04-28 월요일)
- 추가 센서 연결 (addr=0x04부터)
- 데이터 DB 저장 검토 (SQLite 등)
- 웹 대시보드 이력 그래프 개선

---

#### 토양 센서 baud rate 9600 영구 변경 ✅
- 레지스터 `0x07D1` (설정 레지스터) 발견 — 데이터시트 입수로 해결
- 인코딩: `0x0000`=2400 / `0x0001`=4800 / `0x0002`=9600
- 명령: `01 06 07 D1 00 02 59 46` → 전원 재시작 후 영구 적용
- 삽질 기록: 0x0007(살리니티 데이터 레지스터)을 baud 레지스터로 착각하고 여러 번 write 시도했으나 실패. 데이터시트 확인 후 0x07D1이 정확한 주소임을 확인

#### 토양 센서 Modbus 주소 0x01 → 0x02 변경 ✅
- 레지스터 `0x07D0` (Slave ID 레지스터)
- 명령: `01 06 07 D0 00 02 08 86`

#### 두 센서 RS485 버스 통합 ✅
- 온습도(addr=0x01, 9600) + 토양(addr=0x02, 9600) 같은 A/B 버스에 병렬 연결
- `firmware/rp2040_main.py` → 통합 펌웨어로 교체

#### 웹 대시보드 전면 개편 ✅
- 9개 항목 카드: AirTemp / Humidity / Moisture / SoilTemp / EC / pH / N / P / K
- 실시간 차트: 4개 라인 (AirTemp, Humidity, Moisture, SoilTemp)
- Regex 파싱: `AirTemp:X | Humidity:X% || Moisture:X% | SoilTemp:X | EC:X | pH:X | N:X P:X K:X`

---

### 현재 최종 상태

| 항목 | 값 |
|---|---|
| RS485 버스 | 1개 (A/B 공유) |
| UART | UART0, GP0(TX)/GP1(RX), 9600 baud |
| 온습도 센서 | addr=0x01, reg 0x0000~0x0001 |
| 토양 센서 | addr=0x02, reg 0x0000~0x0006 |
| 출력 주기 | 약 2.5초 |

---

### 내일/다음 할 일

- 추가 센서 연결 예정 (addr=0x03부터 순서대로 할당)
- 데이터 DB 저장 검토 (SQLite 등)
- 웹 대시보드 데이터 이력 그래프 추가 검토

---

## 2026-04-23 (1일차)

### 완료된 작업

#### 환경 세팅
- RP2040 Zero USB 연결 확인 (`/dev/cu.usbmodem101`)
- Python 가상환경 `.venv` 구성 (pyserial, flask, flask-socketio, mpremote)
- `upload.py` 제작 → mpremote 없이 pyserial로 직접 RP2040 펌웨어 업로드 가능
- `mac_monitor.py` 개선 → 연결 끊김 시 자동 재연결 처리

#### 웹 대시보드 버그 수정
- `web_monitor.py` JS 코드 안에 Python 문법(`True/False`) → `true/false` 수정

#### 온습도 센서 ✅ 완료
- RS485 Modbus RTU 통신 성공
- **Baud Rate: 9600 / 주소: 0x01**
- 레지스터 0x0000 = 습도, 0x0001 = 온도
- 담당 코드: `rp2040_temp_humidity.py`

#### 토양 5 in 1 센서 ⚠️ 부분 완료
- RS485 Modbus RTU 통신 성공
- **Baud Rate: 4800 / 주소: 0x01**
- 레지스터: 수분, 온도, EC, pH, N, P, K (7개)
- 담당 코드: `rp2040_soil.py`

---

### 배선 상태 (1일차 기준 → 이후 변경 없음)

| 구분 | 연결 |
|---|---|
| RS485 모듈 TX | RP2040 GP1 (RX) |
| RS485 모듈 RX | RP2040 GP0 (TX) |
| RS485 모듈 VCC | RP2040 5V |
| RS485 모듈 GND | 공통 GND |
| 센서 VCC | RP2040 5V |
| 센서 GND | 공통 GND |
| 센서 A | 모듈 A |
| 센서 B | 모듈 B |
