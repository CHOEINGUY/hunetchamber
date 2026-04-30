from machine import SoftSPI, Pin
import wiznet5k
import time

spi = SoftSPI(baudrate=100_000, polarity=1, phase=1,
              sck=Pin(26), mosi=Pin(3), miso=Pin(4))
cs  = Pin(29, Pin.OUT)
rst = Pin(28, Pin.OUT)

rst.value(0); time.sleep(0.5); rst.value(1); time.sleep(1)

print("W5500 초기화...")
eth = wiznet5k.WIZNET5K(spi, cs, reset=None, is_dhcp=False)
print("SPI OK")

def read_phy():
    val = eth.read(0x002E, 0x00)[0]
    lnk = val & 0x01
    spd = (val >> 1) & 0x01
    dpx = (val >> 2) & 0x01
    omc = (val >> 3) & 0x07
    print(f"    PHYCFGR=0x{val:02X}  OPMDC={omc:03b}  DPX={dpx}  SPD={spd}  LNK={lnk}")
    return lnk

def set_phy(opmdc):
    # PHY reset with new mode
    eth.write(0x002E, 0x04, 0x40 | (opmdc << 3))  # OPMD=1, RST=0
    time.sleep(0.15)
    eth.write(0x002E, 0x04, 0xC0 | (opmdc << 3))  # OPMD=1, RST=1
    time.sleep(3)

modes = [
    (7, "Auto-Neg (all capable)"),
    (5, "100BT Full Duplex (forced)"),
    (4, "100BT Half Duplex (forced)"),
    (3, "10BT Full Duplex (forced)"),
    (2, "10BT Half Duplex (forced)"),
]

for opmdc, name in modes:
    print(f"\n>>> {name}")
    set_phy(opmdc)
    linked = False
    for i in range(5):
        lnk = read_phy()
        if lnk:
            print(f"    *** LINK UP! ***")
            linked = True
            break
        time.sleep(1)
    if not linked:
        print("    링크 없음")

print("\n=== 완료 ===")
