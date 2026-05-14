# 데이터 흐름 및 통신 아키텍처 (Data Flow)

본 시스템은 저전력 마이크로컨트롤러(Pico WH)와 게이트웨이(Pi 4) 간의 효율적인 데이터 교환을 위해 다음과 같은 구조를 가집니다.

---

## 📤 1. 상향 스트림 (Pico → Gateway)
- **주기:** 1,000ms (1Hz)
- **방식:** HTTP POST (JSON Payload)
- **특징:** 단순 온습도뿐 아니라 현재 제어 상태(Armed, Auto, SSR Status)와 보호 로직 잔여 시간(Wait Time)을 포함하여 게이트웨이가 장치의 내부 상태를 완벽히 미러링하게 함.

## 📥 2. 하향 스트림 (Gateway → Pico) - 'Response Injection'
- **방식:** Pico가 POST를 보낸 직후의 **HTTP Response body**에 명령을 주입하여 전달.
- **이유:** Pico가 서버 역할을 하여 포트를 개방할 경우 보안 취약점이 발생할 수 있으므로, 클라이언트 요청에 응답을 싣는 방식을 채택하여 방화벽/네트워크 설정 문제를 원천 차단함.

## 💾 3. 저장 및 시각화
- **DB:** MariaDB에 고해상도(1s)로 적재하여, 추후 냉각 효율 분석 및 기기 고장 예후 진단(Predictive Maintenance)을 위한 기초 데이터 확보.
