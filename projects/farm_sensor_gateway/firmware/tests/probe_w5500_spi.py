from machine import SPI, Pin
import time

try:
    from machine import SoftSPI
except ImportError:
    SoftSPI = None

CS_PIN = 29
RST_PIN = 28

TESTS = [
    ("actual_softspi_mode0_100k", "soft", 26, 3, 4, 0, 0, 100_000),
    ("actual_softspi_mode1_100k", "soft", 26, 3, 4, 0, 1, 100_000),
    ("actual_softspi_mode2_100k", "soft", 26, 3, 4, 1, 0, 100_000),
    ("actual_softspi_mode3_100k", "soft", 26, 3, 4, 1, 1, 100_000),
    ("actual_softspi_mode3_500k", "soft", 26, 3, 4, 1, 1, 500_000),
    ("actual_softspi_mode3_1m", "soft", 26, 3, 4, 1, 1, 1_000_000),
    ("actual_softspi_swap_mosi_miso", "soft", 26, 4, 3, 0, 0, 100_000),
    ("expected_spi0_mode0", 0, 2, 3, 4, 0, 0, 100_000),
    ("expected_spi0_mode3", 0, 2, 3, 4, 1, 1, 100_000),
    ("old_spi1_mode0", 1, 26, 27, 28, 0, 0, 100_000),
]

def read_reg(spi, cs, addr, block=0x00):
    cs.value(0)
    spi.write(bytes([addr >> 8, addr & 0xFF, block]))
    value = bytearray(1)
    spi.readinto(value)
    cs.value(1)
    return value[0]

def write_reg(spi, cs, addr, block, value):
    cs.value(0)
    spi.write(bytes([addr >> 8, addr & 0xFF, block, value]))
    cs.value(1)

def reset_chip(cs=None):
    if cs:
        cs.value(1)
    rst = Pin(RST_PIN, Pin.OUT)
    rst.value(0)
    time.sleep(0.3)
    rst.value(1)
    time.sleep(0.8)

for name, bus, sck, mosi, miso, polarity, phase, baudrate in TESTS:
    print("\n== {}: SPI{} SCK={} MOSI={} MISO={} ==".format(name, bus, sck, mosi, miso))
    try:
        cs = Pin(CS_PIN, Pin.OUT)
        cs.value(1)
        reset_chip(cs)
        if bus == "soft":
            if not SoftSPI:
                print("ERROR: SoftSPI 없음")
                continue
            spi = SoftSPI(baudrate=baudrate, polarity=polarity, phase=phase,
                          sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
        else:
            spi = SPI(bus, baudrate=baudrate, polarity=polarity, phase=phase,
                      sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))

        mr0 = read_reg(spi, cs, 0x0000, 0x00)
        ver = read_reg(spi, cs, 0x0039, 0x00)
        write_reg(spi, cs, 0x0000, 0x04, 0x08)
        time.sleep(0.05)
        mr8 = read_reg(spi, cs, 0x0000, 0x00)
        write_reg(spi, cs, 0x0000, 0x04, 0x10)
        time.sleep(0.05)
        mr10 = read_reg(spi, cs, 0x0000, 0x00)
        write_reg(spi, cs, 0x0000, 0x04, 0x00)

        print("MR0=0x{:02X} VERSION=0x{:02X} MR_after_08=0x{:02X} MR_after_10=0x{:02X}".format(
            mr0, ver, mr8, mr10
        ))
    except Exception as e:
        print("ERROR:", e)

if SoftSPI:
    print("\n== soft_swap: SCK=2 MOSI=4 MISO=3 ==")
    try:
        cs = Pin(CS_PIN, Pin.OUT)
        cs.value(1)
        reset_chip(cs)
        spi = SoftSPI(baudrate=100_000, polarity=0, phase=0,
                      sck=Pin(2), mosi=Pin(4), miso=Pin(3))

        mr0 = read_reg(spi, cs, 0x0000, 0x00)
        ver = read_reg(spi, cs, 0x0039, 0x00)
        write_reg(spi, cs, 0x0000, 0x04, 0x08)
        time.sleep(0.05)
        mr8 = read_reg(spi, cs, 0x0000, 0x00)
        write_reg(spi, cs, 0x0000, 0x04, 0x10)
        time.sleep(0.05)
        mr10 = read_reg(spi, cs, 0x0000, 0x00)
        write_reg(spi, cs, 0x0000, 0x04, 0x00)

        print("MR0=0x{:02X} VERSION=0x{:02X} MR_after_08=0x{:02X} MR_after_10=0x{:02X}".format(
            mr0, ver, mr8, mr10
        ))
    except Exception as e:
        print("ERROR:", e)
else:
    print("\nSoftSPI 없음")
