from machine import SoftSPI, Pin
import wiznet5k
import time

spi = SoftSPI(baudrate=100_000, polarity=1, phase=1,
              sck=Pin(26), mosi=Pin(3), miso=Pin(4))
cs  = Pin(29, Pin.OUT)
rst = Pin(28, Pin.OUT)

# RST 처리
rst.value(0)
time.sleep(0.2)
rst.value(1)
time.sleep(0.5)

print("W5500 초기화 중...")
try:
    eth = wiznet5k.WIZNET5K(spi, cs, reset=None, is_dhcp=False)
    # 정적 IP 설정
    eth.ifconfig = (
        b'\xc0\xa8\x00\x50',  # IP: 192.168.0.80
        b'\xff\xff\xff\x00',  # Subnet: 255.255.255.0
        b'\xc0\xa8\x00\x01',  # GW: 192.168.0.1
        b'\xc0\xa8\x00\x01',  # DNS: 192.168.0.1
    )
    print("IP 설정 완료: 192.168.0.80")
    print("연결 성공!")
except Exception as e:
    print("오류:", e)
