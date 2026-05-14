# 데이터 흐름

## 전체 흐름

```
[RS485 온습도 센서 addr=1]
        ↓ RS485 UART0 (9600 baud)
[Pico WH / RP2040]  ──── RS485 UART1 (115200 baud) ────→  [RP2350 Touch LCD]
        ↓                                                          ↑
    Wi-Fi HTTP POST /fridge                              명령 전송 ←── 터치 입력
        ↓
[Raspberry Pi :8081]
   fridge_gateway_server.py
        ↓ INSERT
[MariaDB fridge_readings]
        ↓
[웹 대시보드 http://192.168.100.30:8081/]
```

## 제어 방향

- **Pico**가 온도를 읽고 SSR 출력을 결정한다.
- **RP2350**은 상태를 표시하고 명령을 Pico에 전달한다.
- **웹 대시보드**는 읽기 전용 모니터링이다 (제어 명령 경로 없음).
- **Wi-Fi/DB 전송 실패**는 Pico의 제어 루프에 영향을 주지 않는다.

이유: DB/네트워크 장애가 냉장고 제어를 멈추게 하면 안 되기 때문이다.

## 로깅 경로

| 항목 | 값 |
|---|---|
| 게이트웨이 IP:Port | 192.168.100.30:8081 |
| 엔드포인트 | POST /fridge |
| 기록 주기 | 1초 (테스트 단계) |
| DB 테이블 | fridge_readings |
| 대시보드 | http://192.168.100.30:8081/ |
| 헬스 체크 | http://192.168.100.30:8081/health |
| API | http://192.168.100.30:8081/api/readings?limit=50 |

## DB 주요 컬럼

| 컬럼 | 내용 |
|---|---|
| created_at | 기록 시각 |
| device_id | 기기 ID (fridge-01) |
| temp_c | 센서 온도 |
| humidity | 습도 |
| target_c | 목표 온도 |
| fridge_on | SSR 출력 상태 (0/1) |
| armed | armed 상태 (0/1) |
| auto_mode | 자동 제어 상태 (0/1) |
| reason | 상태 변화 이유 |

## Pico STATUS 프로토콜

Pico가 RP2350에 2초 주기로 전송하는 상태 줄 형식:

```text
STATUS on=0 armed=0 auto=0 target_c=15.0 band_c=0.5 min_off_s=300 wait_on_s=0 min_on_s=300 wait_off_s=0 state_elapsed_s=311 temp_c=26.8 humidity=38.2 sensor_age_s=6 fan=0 led=0 reason=boot
```

## 보안 설계

- DB 접속 정보(비밀번호)는 Raspberry Pi에만 있다. Pico는 HTTP POST만 사용한다.
- Wi-Fi 비밀번호는 `controller/pico_wh/wifi_config.py`에만 있으며 `.gitignore` 포함이다.
