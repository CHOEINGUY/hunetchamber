import serial
import serial.tools.list_ports
import time

def find_rp2040_port():
    ports = serial.tools.list_ports.comports()
    candidates = [port.device for port in ports if "usbmodem" in port.device.lower()]
    return candidates[0] if candidates else None

def main():
    print("🔍 RP2040 모니터 시작... (Ctrl+C로 종료)")
    baud = 115200

    while True:
        port = find_rp2040_port()
        if not port:
            print("⏳ RP2040 연결 대기 중...")
            time.sleep(2)
            continue

        print(f"✅ RP2040 연결됨: {port}")
        try:
            ser = serial.Serial(port, baud, timeout=1)
            ser.flushInput()
            while True:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        print(f"📥 {line}")
                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n👋 종료.")
            break
        except Exception:
            print("🔄 연결 끊김, 재연결 중...")
            time.sleep(2)

if __name__ == "__main__":
    main()
