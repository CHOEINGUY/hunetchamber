import argparse
import serial
import serial.tools.list_ports
import time

TARGET = 'main.py'

DEFAULT_SOURCE = 'firmware/rp2040_main.py'

def find_rp2040_port():
    ports = serial.tools.list_ports.comports()
    candidates = [p.device for p in ports if "usbmodem" in p.device.lower()]
    return candidates[0] if candidates else None

def wait_for(ser, marker, timeout=3.0):
    buf = b''
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = ser.read(256)
        if data:
            buf += data
            if marker in buf:
                return buf
    return buf

parser = argparse.ArgumentParser()
parser.add_argument("source", nargs="?", default=DEFAULT_SOURCE)
parser.add_argument("--port", default=None)
args = parser.parse_args()

source = args.source
port = args.port or find_rp2040_port()
if not port:
    print("FAILED to find RP2040 serial port.")
    exit(1)

with open(source, 'r') as f:
    content = f.read()

print(f"Uploading {source} -> {TARGET} via {port} ...")

with serial.Serial(port, 115200, timeout=0.5) as ser:
    # Interrupt + enter raw REPL
    ser.write(b'\r\x03\x03\x01')
    resp = wait_for(ser, b'raw REPL', timeout=3.0)

    if b'raw REPL' not in resp:
        # Try soft reset path
        ser.write(b'\x04')
        resp = wait_for(ser, b'raw REPL', timeout=5.0)

    if b'raw REPL' not in resp:
        print(f"FAILED to enter raw REPL. Got: {resp}")
        exit(1)

    print("In raw REPL. Writing file...")

    write_cmd = f"f=open({repr(TARGET)},'w');f.write({repr(content)});f.close();print('DONE')\n"
    ser.write(write_cmd.encode('utf-8'))
    ser.write(b'\x04')

    resp = wait_for(ser, b'DONE', timeout=10.0)

    if b'DONE' in resp:
        print("Upload successful! Resetting board...")
        ser.write(b'\x02')
        time.sleep(0.3)
        ser.write(b'\x04')
        print("Board reset. Done.")
    else:
        print(f"Upload failed. Got: {resp}")
