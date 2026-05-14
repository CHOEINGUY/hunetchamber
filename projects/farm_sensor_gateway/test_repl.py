import serial, time

s = serial.Serial('/dev/cu.usbmodem101', 115200, timeout=3)
time.sleep(0.5)

# Ctrl+C 여러번
for _ in range(5):
    s.write(b'\x03')
    time.sleep(0.2)

# 뭐라고 응답하나 확인
s.write(b'\r\n')
time.sleep(1)
out = s.read(500)
print("응답:", repr(out))

s.close()
