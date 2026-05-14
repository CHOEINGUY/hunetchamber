# RP2350 Fridge Dashboard

RP2350 Touch LCD는 Pico 냉장고 컨트롤러의 터치 리모컨 겸 상태 디스플레이다.
제어 판단은 Pico가 하고, RP2350은 상태 표시와 명령 전달만 한다.

## 소스 코드 위치

실제 C 소스는 `RP2350-Touch-LCD-4/` 아래에 있다.

```text
소스: RP2350-Touch-LCD-4/examples/fridge_dashboard/fridge_dashboard.c
빌드: RP2350-Touch-LCD-4/build-fridge/examples/fridge_dashboard/fridge_dashboard.uf2
```

빌드 방법과 RS485 링크 핀 정보는 [`../docs/04_DASHBOARD.md`](../docs/04_DASHBOARD.md)를 참고한다.

## 왜 별도 폴더인가

RP2350 C 코드는 Waveshare SDK 기반이라 `RP2350-Touch-LCD-4/` 루트에서 CMake로 빌드해야 한다.
`fridge_controller/` 안으로 옮기면 빌드 경로가 깨진다. 이 폴더는 링크/문서 역할만 한다.
