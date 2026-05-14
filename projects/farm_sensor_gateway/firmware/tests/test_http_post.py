from machine import SoftSPI, Pin
import wiznet5k
import wiznet5k_socket as socket
import json
import time

spi = SoftSPI(baudrate=100_000, polarity=1, phase=1,
              sck=Pin(26), mosi=Pin(3), miso=Pin(4))
cs  = Pin(29, Pin.OUT)
rst = Pin(28, Pin.OUT)

rst.value(0)
time.sleep(0.5)
rst.value(1)
time.sleep(1)

print("W5500 초기화...")
eth = wiznet5k.WIZNET5K(spi, cs, reset=None, is_dhcp=True, debug=False)
socket.set_interface(eth)

print("DHCP 설정 완료")
print("MAC:", eth.mac_address)
print("IFCONFIG:", eth.ifconfig)

# PHY 강제 설정: OPMD=1, OPMDC=111 (all capable, auto-neg)
print("PHY 재설정 중...")
eth.write(0x002E, 0x04, 0x78)  # RST=0 (PHY reset)
time.sleep(0.1)
eth.write(0x002E, 0x04, 0xF8)  # RST=1, OPMD=1, OPMDC=111
time.sleep(3)

for i in range(10):
    phycfgr = eth.read(0x002E, 0x00)[0]
    lnk = phycfgr & 0x01
    print("  {}초: PHYCFGR=0x{:02X} LNK={}".format(i + 1, phycfgr, lnk))
    if lnk:
        print("링크 UP")
        break
    time.sleep(1)

wiznet5k.WIZNET5K.link_status = property(lambda self: 1)

SERVER = '192.168.100.29'
PORT   = 8080
data   = json.dumps({
    "source": "w5500-test",
    "air_temp": 25.3,
    "humidity": 55.1,
    "co2": 412,
    "relay": 0,
})
req    = (
    f"POST /sensor HTTP/1.1\r\n"
    f"Host: {SERVER}\r\n"
    f"Content-Type: application/json\r\n"
    f"Content-Length: {len(data)}\r\n"
    f"Connection: close\r\n\r\n"
    f"{data}"
)

print("HTTP POST 전송 중... {}:{}".format(SERVER, PORT))
try:
    s = socket.socket()
    s.settimeout(2)
    s.connect((SERVER, PORT))
    s.send(req.encode())
    time.sleep(1)
    resp = s.recv(256)
    s.close()
    print("응답:", resp[:80])
    print("전송 완료")
except Exception as e:
    print("오류:", e)
