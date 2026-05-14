# 🧊 냉장고 제어 시스템 (Fridge Controller)

이 프로젝트는 Raspberry Pi Pico WH를 사용하여 냉장고의 온도를 정밀하게 제어하고, 데이터를 게이트웨이로 전송하여 실시간으로 모니터링하는 시스템입니다.

---

## 🛡️ 안전 및 보호 로직 (Safety First)

시스템의 기계적 보호를 위해 아래 로직은 **온도 제어 조건보다 항상 우선**하여 적용됩니다.

| 보호 항목 | 상세 내용 | 이유 |
| :--- | :--- | :--- |
| **최소 OFF 시간** | **300초** (OFF 후 5분간 재가동 금지) | 컴프레셔의 잦은 재기동으로 인한 기계적 손상 방지 |
| **최소 ON 시간** | **300초** (ON 후 5분간 정지 금지) | 냉각 사이클의 안정적 확보 및 컴프레셔 보호 |
| **안전 잠금 (Armed)** | `armed=0` 시 모든 SSR 출력 강제 차단 | 오작동 방지 및 수동 정비 시 안전 확보 |
| **강제 종료 (Forceoff)** | 즉시 정지 + `disarm` 상태 진입 | 비상 상황 시 즉각적인 대응 |

> **구현 위치:** [`controller/pico_wh/main.py`](controller/pico_wh/main.py) 의 `control_fridge()` 함수

---

## 🔄 데이터 흐름 (Data Flow)

```text
[ 하드웨어 계층 ]                  [ 통신 계층 ]                  [ 서버/UI 계층 ]
+-------------------+          +------------------+          +--------------------+
| RS485 온습도 센서  |  UART0   |  Pico WH (제어)   |  HTTP    |  Raspberry Pi 4    |
| (Address 1)       | -------->| (W5100S-EVB-Pico)| -------->| (Gateway Server)   |
+-------------------+ (9600bps) +------------------+ (POST)   +---------+----------+
                                       |                             |
                                       | RS485 UART1                 | MariaDB
                                       v                             v
                                +------------------+          +--------------------+
                                | RP2350 Touch LCD |          | 웹 대시보드 (Vite)  |
                                | (로컬 대시보드)   |          | (원격 모니터링)     |
                                +------------------+          +--------------------+
```

---

## 📂 파일 가이드 (Role-based)

### 1. 핵심 제어 (Core Control)
- **[`controller/pico_wh/main.py`](controller/pico_wh/main.py)**: 냉장고 제어 메인 로직, 안전 보호기, 게이트웨이 통신.
- **[`docs/01_CONTROL_LOGIC.md`](docs/01_CONTROL_LOGIC.md)**: 제어 알고리즘 및 명령어 상세 설명.

### 2. 게이트웨이 및 데이터 (Gateway & DB)
- **[`gateway/fridge_gateway_server.py`](gateway/fridge_gateway_server.py)**: HTTP POST 수신 및 DB 저장, 대시보드 API.
- **[`gateway/setup_fridge_db.py`](gateway/setup_fridge_db.py)**: MariaDB 테이블 스키마 및 초기 설정.

### 3. 대시보드 및 UI (Dashboard)
- **[`dashboard_vite/`](dashboard_vite/)**: 최신 웹 모니터링 대시보드 소스 (React/Vite).
- **[`rp2350_dashboard/`](rp2350_dashboard/)**: RP2350 기반 LCD 패널 제어 관련 문서.

### 4. 아카이브 및 기타 (Maintenance)
- **[`archive/`](archive/)**: 이전 버전의 제어 코드 및 백업.
- **[`controller/pico_wh/tools/`](controller/pico_wh/tools/)**: 센서 주소 변경 및 진단용 유틸리티.

---

## 🚦 현재 상태 및 다음 단계

### ✅ 동작 중인 기능
- 1초 주기의 실시간 온도 수집 및 DB 저장.
- 컴프레셔 보호 로직 (Min ON/OFF) 적용 완료.
- 원격 웹 대시보드 가동 중 (`http://192.168.100.30:8081/`).

### 🚀 다음 단계 (Next Steps)
1. **센서 Fail-safe 정의**: 센서 데이터가 유실되거나 지연될 경우의 안전 동작(예: 강제 OFF) 구현.
2. **데이터 분석**: SSR ON→OFF 전환 시의 온도 하강 관성 패턴 분석.
3. **이중화**: 현재 단일 센서(addr=1)에서 보조 센서(addr=2)를 포함한 평균값 제어로 확장.

---

## 🛠️ 리뷰어 퀵 명령어

### 1. 실시간 상태 점검 (Raspberry Pi)
```bash
# 게이트웨이 서비스 로그 확인
ssh pi@192.168.100.30 'journalctl -u fridge-gateway.service -f'

# DB 최신 수집 데이터 5건 확인
ssh pi@192.168.100.30 'mysql -u smart_chamber -p smart_chamber -e "SELECT created_at, temp_c, fridge_on, reason FROM fridge_readings ORDER BY id DESC LIMIT 5;"'
```

### 2. 로컬 개발 및 진단
```bash
# Pico 펌웨어 실시간 로그 모니터링
.venv/bin/mpremote connect /dev/cu.usbmodem101 repl

# 대시보드 로컬 실행 (Node.js 필요)
cd projects/fridge_controller/dashboard_vite && npm install && npm run dev
```

---

## ⚠️ 리스크 및 관찰 포인트

| 관찰 항목 | 리스크 수준 | 상세 내용 |
| :--- | :--- | :--- |
| **센서 에러 대응** | **높음** | 현재 센서 끊김 시 이전 상태를 유지함. Fail-safe 로직 시급. |
| **DB 쓰기 부하** | 보통 | 1초 주기의 쓰기 작업이 SD 카드 수명에 미치는 영향 모니터링 중. |
| **WiFi 안정성** | 보통 | 공유기와의 거리에 따른 데이터 유실 여부 관찰 중. |

---
*참고: Wi-Fi 및 DB 비밀번호는 `wifi_config.py` 및 서버 환경변수로 관리하며, 저장소에 노출하지 않습니다.*
