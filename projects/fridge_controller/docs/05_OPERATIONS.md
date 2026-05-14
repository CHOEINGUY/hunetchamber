# 운영 및 배포

## 왜 Raspberry Pi를 거치는가

- MacBook을 켜둘 필요가 없다.
- Pico는 HTTP POST만 하면 된다. DB 프로토콜, 인증, 재접속 처리를 MicroPython에 넣지 않아도 된다.
- DB 접속 정보가 Raspberry Pi에만 있어 Pico에 노출되지 않는다.

## Raspberry Pi 초기 설치

Pi에 SSH로 접속 후:

```sh
cd /home/pi/Hunet
python3 -m venv .venv
.venv/bin/pip install -r fridge_controller/gateway/requirements.txt
.venv/bin/python fridge_controller/gateway/setup_fridge_db.py
```

## 서버 실행

```sh
.venv/bin/python -u fridge_controller/gateway/fridge_gateway_server.py
```

## systemd 서비스 등록 (재시작 시 자동 기동)

```sh
sudo nano /etc/systemd/system/fridge-gateway.service
```

내용:

```ini
[Unit]
Description=Hunet Fridge Gateway
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/pi/Hunet
ExecStart=/home/pi/Hunet/.venv/bin/python -u /home/pi/Hunet/fridge_controller/gateway/fridge_gateway_server.py
Restart=always
RestartSec=3
Environment=FRIDGE_HTTP_HOST=0.0.0.0
Environment=FRIDGE_HTTP_PORT=8081

[Install]
WantedBy=multi-user.target
```

등록 및 시작:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now fridge-gateway.service
```

## 상태 확인 명령어

```sh
# 서비스 상태
sudo systemctl status fridge-gateway.service

# 헬스 체크
curl http://127.0.0.1:8081/health

# DB 최신 5 row
mysql -u smart_chamber -psmart_chamber smart_chamber \
  -e "SELECT id, created_at, temp_c, fridge_on, reason FROM fridge_readings ORDER BY id DESC LIMIT 5;"

# 실시간 로그
journalctl -u fridge-gateway.service -f
```

## DB 접속 환경변수

비밀번호는 문서에 기록하지 않는다. 환경변수로 설정한다.

```text
HUNET_DB_HOST     (기본값 있음)
HUNET_DB_PORT     (기본값 있음)
HUNET_DB_USER     (기본값 있음)
HUNET_DB_PASSWORD ← 환경변수로 설정 권장
HUNET_DB_NAME     (기본값 있음)
```

## Pico 업로드

```sh
python3 upload.py fridge_controller/controller/pico_wh/main.py --port /dev/cu.usbmodem101
```

Pico W MicroPython 필요. 일반 Pico MicroPython이면 `network` 모듈이 없어 Wi-Fi가 동작하지 않는다.

## Mac → Pi 코드 배포 (rsync)

```sh
rsync -av \
  --exclude .venv/ \
  --exclude RP2350-Touch-LCD-4/build/ \
  --exclude .git/ \
  --exclude __pycache__/ \
  --exclude '*.pyc' \
  --exclude .DS_Store \
  --exclude '*.pdf' \
  /Users/choeingyumac/Hunet/ pi@192.168.100.30:/home/pi/Hunet/
```

## 테스트 INSERT (curl)

```sh
curl -X POST http://127.0.0.1:8081/fridge \
  -H 'Content-Type: application/json' \
  -d '{
    "device_id":"fridge-01",
    "temp_c":15.2,
    "humidity":45.0,
    "target_c":15.0,
    "band_c":0.5,
    "fridge_on":0,
    "armed":0,
    "auto_mode":0,
    "fan_percent":0,
    "led_percent":0,
    "min_off_s":300,
    "wait_on_s":0,
    "min_on_s":300,
    "wait_off_s":0,
    "state_elapsed_s":300,
    "sensor_age_s":0,
    "reason":"curl_test"
  }'
```

## Pico WH 주의사항

- Pico W 전용 MicroPython 필요
- Wi-Fi 비밀번호: `fridge_controller/controller/pico_wh/wifi_config.py` (`.gitignore` 포함)
- Wi-Fi/POST 실패는 냉장고 제어 루프에 영향을 주지 않는다
- USB 시리얼 모니터를 열어도 제어/로깅 루프가 멈추지 않는다 (논블로킹)
