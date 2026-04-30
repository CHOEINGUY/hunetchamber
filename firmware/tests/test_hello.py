from machine import Pin
import time

led = Pin(25, Pin.OUT)
print("Pico 실행 중")
for i in range(5):
    led.toggle()
    print("tick", i)
    time.sleep(1)
print("완료")
