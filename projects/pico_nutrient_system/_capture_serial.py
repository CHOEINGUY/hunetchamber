"""Capture serial output from Pico for N seconds after a soft reset."""
import serial
import time
import sys

PORT = "COM4"
BAUD = 115200
DURATION = 18

ser = serial.Serial(PORT, BAUD, timeout=0.2)
time.sleep(0.3)

# Ctrl+C twice to stop any running program, then Ctrl+D for soft reset
ser.write(b"\x03\x03")
time.sleep(0.2)
ser.reset_input_buffer()
ser.write(b"\x04")

end = time.time() + DURATION
buf = b""
while time.time() < end:
    chunk = ser.read(512)
    if chunk:
        buf += chunk
        try:
            sys.stdout.write(chunk.decode("utf-8", "ignore"))
            sys.stdout.flush()
        except Exception:
            pass
ser.close()
print("\n--- capture end ---")
