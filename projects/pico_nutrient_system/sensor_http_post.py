# Pico WH MicroPython example for the future Wi-Fi logging step.
# This is intentionally not imported by pico/main.py yet.

import json
import network
import socket
import time


WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
GATEWAY_HOST = "192.168.100.30"
GATEWAY_PORT = 8081
GATEWAY_PATH = "/fridge"


def connect_wifi(ssid=WIFI_SSID, password=WIFI_PASSWORD, timeout_s=20):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        deadline = time.time() + timeout_s
        while not wlan.isconnected() and time.time() < deadline:
            time.sleep(0.25)
    if not wlan.isconnected():
        raise RuntimeError("wifi_connect_failed")
    return wlan.ifconfig()


def post_json(host, port, path, data, timeout_s=3):
    body = json.dumps(data)
    request = (
        "POST {} HTTP/1.1\r\n"
        "Host: {}\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n"
        "\r\n"
        "{}"
    ).format(path, host, len(body), body)

    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket()
    try:
        s.settimeout(timeout_s)
        s.connect(addr)
        s.send(request.encode())
        return s.recv(128)
    finally:
        s.close()


def example():
    connect_wifi()
    payload = {
        "device_id": "fridge-01",
        "temp_c": 15.2,
        "humidity": 44.8,
        "target_c": 15.0,
        "band_c": 0.5,
        "fridge_on": 0,
        "armed": 0,
        "auto_mode": 0,
        "fan_percent": 0,
        "led_percent": 0,
        "min_off_s": 300,
        "wait_on_s": 0,
        "min_on_s": 300,
        "wait_off_s": 0,
        "state_elapsed_s": 300,
        "sensor_age_s": 0,
        "reason": "example",
    }
    print(post_json(GATEWAY_HOST, GATEWAY_PORT, GATEWAY_PATH, payload))


if __name__ == "__main__":
    example()
