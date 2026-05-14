# 대시보드

## 웹 대시보드 (Raspberry Pi)

주소: `http://192.168.100.30:8081/`

탭 구성:
- **실시간 상태**: 최신 DB row + 최근 10분 미니 차트
- **데이터 분석**: 기간 필터, 온도/목표/SSR 상태 그래프, 요약 카드, row 테이블

API:

```text
GET http://192.168.100.30:8081/api/readings?limit=50
```

차트 라이브러리: Apache ECharts (CDN)

## RP2350 Touch LCD 대시보드

Pico 옆에 붙어 있는 터치 리모컨이다. Pico와 RS485 UART1로 연결된다.

역할: Pico의 상태를 표시하고 명령을 전달한다. 제어 판단은 Pico가 내린다.

### 터치 컨트롤

| 버튼 | 기능 |
|---|---|
| `-0.5C` / `+0.5C` | 목표 온도 변경 (0~25 C 범위 내) |
| `AUTO` | 자동 온도 제어 ON/OFF |
| `ARM` | SSR 출력 허용/차단 토글 |
| `FAN OFF` / `FAN ON` | 팬 제어 |
| `LED -` / `LED +` | LED PWM ±10% |
| `STATUS` | Pico 즉시 상태 요청 |
| `FORCE OFF` | 즉시 OFF + disarm |

### 응답성 설계

터치 후 Pico 응답을 기다리지 않고 화면을 즉시 갱신한다.  
이유: 터치 반응이 느리게 느껴지는 문제가 있었기 때문이다.

- 터치 콜백에서 UART 직접 쓰기를 하지 않는다.
- 변경값을 큐에 넣고 메인 루프에서 전송한다.
- 반복 터치는 최신 값으로 합산해서 1회만 전송한다.
- Pico STATUS 수신 시 보류 중인 값은 덮어쓰지 않는다.
- `wait_on_s`, `wait_off_s` 등 카운트다운은 Pico 기준값을 받은 후 RP2350에서 로컬로 카운팅한다.

### 펌웨어 빌드

```sh
cd RP2350-Touch-LCD-4
cmake -S . -B build-fridge -DPICO_SDK_PATH=/Users/choeingyumac/Hunet/pico-sdk
cmake --build build-fridge --target fridge_dashboard -j4
cp build-fridge/examples/fridge_dashboard/fridge_dashboard.uf2 /Volumes/RP2350/
```

소스: `RP2350-Touch-LCD-4/examples/fridge_dashboard/fridge_dashboard.c`

### RS485 링크 핀 (RP2350 측)

| 핀 | 기능 |
|---|---|
| UART1 TX (GP8) | Pico 쪽 RS485 모듈로 연결 |
| UART1 RX (GP9) | Pico 쪽 RS485 모듈에서 수신 |
| Baud rate | 115200 |
