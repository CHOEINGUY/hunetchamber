# 🏛️ Hunet Chamber Project Workspace

이 워크스페이스는 농장 환경 제어 및 모니터링을 위한 여러 하부 프로젝트를 포함하고 있습니다.

---

## 📂 프로젝트 구조 (Projects)

| 프로젝트 | 설명 | 주요 기술 |
| :--- | :--- | :--- |
| **[🧊 Fridge Controller](./projects/fridge_controller)** | 냉장고 정밀 온도 제어 및 안전 시스템 | Pico WH, RS485, React, MariaDB |
| **[🌾 Farm Gateway](./projects/farm_sensor_gateway)** | 농장 온습도/CO2 센서 수집 게이트웨이 | Raspberry Pi, Python, W5500 |

---

## 📚 연구 기록 (Research Records)

프로젝트의 진행 과정과 기술적 의사결정을 날짜별로 기록한 문서입니다.
- **[✍️ 연구일지 (Research Diary)](./research_diary)**: 2026-04-20부터 현재까지의 일일 연구 기록 (기록자: 최인규).

---

## 📦 공용 및 외부 라이브러리 (Shared & Vendor)

- **[`/shared`](./shared)**: 여러 프로젝트에서 공통으로 사용하는 유틸리티 및 설정.
- **[`/vendor`](./vendor)**: 외부 하드웨어 제조사 SDK 및 타사 라이브러리.
  - [`waveshare_lcd_sdk`](./vendor/waveshare_lcd_sdk): RP2350 Touch LCD 4인치용 BSP 및 예제.

---

## 📜 아카이브 (Archive)

과거의 코드, 레거시 구현체 및 참조용 백업 데이터는 **[`/archive`](./archive)** 폴더에서 확인할 수 있습니다.
- [Farm Gateway Legacy](./archive/farm_sensor_gateway)
- [Fridge Controller Archive](./archive/fridge_controller)

---

## 🛠️ 워크스페이스 관리

- **보안:** Wi-Fi SSID, DB 비밀번호 등 민감정보는 절대 커밋하지 않습니다. 각 프로젝트의 `README.md` 내 '민감정보 관리' 섹션을 참고하세요.
- **추가:** 새로운 제어 장치가 추가될 경우 `projects/` 폴더 내에 별도 프로젝트로 구성합니다.

---
*Last Updated: 2026-05-14*
