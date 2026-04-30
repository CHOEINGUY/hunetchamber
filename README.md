# Hunet 센서 모니터링 프로젝트

RP2040 Zero + RS485 모듈을 이용한 토양/온습도 센서 데이터 수집 시스템.

---

## 폴더 구조

```
Hunet/
├── firmware/                    ← RP2040에 올라가는 MicroPython 코드
│   ├── rp2040_main.py           업로드 시 이 파일이 보드에 올라감 (upload.py가 참조)
│   ├── rp2040_soil.py           토양 5 in 1 센서 전용 코드
│   ├── rp2040_temp_humidity.py  온습도 센서 전용 코드
│   └── micropython.uf2          MicroPython 부트로더 (보드 초기화 시 사용)
│
├── docs/                        ← 문서
│   ├── SENSORS.md               센서별 배선, Modbus 설정, 레지스터 맵
│   └── DEVLOG.md                날짜별 개발 진행 로그
│
├── mac_monitor.py               터미널에서 RP2040 시리얼 출력 확인
├── web_monitor.py               Flask 기반 웹 대시보드 (브라우저로 확인)
├── upload.py                    firmware/rp2040_main.py를 RP2040에 업로드
└── .venv/                       Python 가상환경 (pyserial, flask 등)
```

---

## 워크플로우

### 센서 코드 변경 & 업로드
1. `firmware/rp2040_soil.py` 또는 `firmware/rp2040_temp_humidity.py` 수정
2. 원하는 파일 내용을 `firmware/rp2040_main.py`에 복사
3. 업로드:
```bash
cd /Users/choeingyumac/Hunet
source .venv/bin/activate
python upload.py
```

### 터미널 모니터링
```bash
cd /Users/choeingyumac/Hunet
source .venv/bin/activate
python mac_monitor.py
```

### 웹 대시보드
```bash
python web_monitor.py
# 브라우저에서 http://127.0.0.1:5001 접속
```

---

## 하드웨어

- **MCU**: Raspberry Pi RP2040 Zero
- **통신 모듈**: TTL-to-RS485 (VCC / RX / TX / GND / A / B)
- **센서 1**: 온습도 RS485 Modbus (baud 9600, addr 0x01)
- **센서 2**: 토양 5 in 1 RS485 Modbus (baud 4800, addr 0x01) ← baud 통일 작업 중

자세한 배선은 `docs/SENSORS.md` 참고.
