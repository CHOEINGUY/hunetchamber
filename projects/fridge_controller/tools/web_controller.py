#!/usr/bin/env python3
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import serial
import serial.tools.list_ports
import threading
import time
from urllib.parse import urlparse


SERIAL_LOCK = threading.Lock()
SERIAL_PORT = None
BAUD = 115200
BRIDGE = None


COMMANDS = {"help", "status", "arm", "disarm", "on", "off", "forceoff", "auto", "target", "fan", "led"}


INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>냉장고 SSR 제어</title>
  <style>
    :root {
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f7f8;
      color: #1c2529;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
    }
    main {
      width: min(620px, calc(100vw - 32px));
      background: #fff;
      border: 1px solid #d9e1e4;
      border-radius: 8px;
      box-shadow: 0 12px 36px rgba(18, 38, 48, 0.08);
      padding: 24px;
    }
    h1 {
      margin: 0 0 18px;
      font-size: 24px;
      letter-spacing: 0;
    }
    .status {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-bottom: 18px;
    }
    .metric {
      border: 1px solid #e1e7ea;
      border-radius: 6px;
      padding: 12px;
      background: #fbfcfc;
    }
    .label {
      color: #65747b;
      font-size: 12px;
      margin-bottom: 6px;
    }
    .value {
      font-size: 22px;
      font-weight: 700;
    }
    .value.on { color: #16833a; }
    .value.off { color: #9aa4a9; }
    .value.warn { color: #b06000; }
    .controls {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }
    .setpoint {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 14px;
    }
    input {
      min-height: 44px;
      border: 1px solid #b8c5ca;
      border-radius: 6px;
      padding: 0 10px;
      font-size: 16px;
    }
    button {
      min-height: 48px;
      border: 1px solid #b8c5ca;
      border-radius: 6px;
      background: #fff;
      color: #172126;
      font-size: 16px;
      font-weight: 650;
      cursor: pointer;
      transition: transform 80ms ease, box-shadow 120ms ease, background 120ms ease, opacity 120ms ease;
    }
    button:hover { background: #f2f6f7; }
    button:active { transform: translateY(1px) scale(0.99); }
    button.busy {
      opacity: 0.68;
      cursor: progress;
      box-shadow: inset 0 0 0 2px rgba(18, 103, 216, 0.24);
    }
    button.primary {
      background: #1267d8;
      border-color: #1267d8;
      color: white;
    }
    button.danger {
      background: #d93025;
      border-color: #d93025;
      color: white;
    }
    pre {
      height: 180px;
      margin: 18px 0 0;
      padding: 12px;
      overflow: auto;
      border-radius: 6px;
      background: #11181c;
      color: #d7f7df;
      font-size: 13px;
      line-height: 1.45;
    }
    .message {
      min-height: 22px;
      margin-top: 14px;
      font-size: 14px;
      font-weight: 650;
      color: #52636b;
    }
    .message.ok { color: #16833a; }
    .message.err { color: #c1261f; }
    @media (max-width: 560px) {
      .status { grid-template-columns: repeat(2, 1fr); }
      .controls { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <h1>냉장고 SSR 제어</h1>
    <section class="status">
      <div class="metric"><div class="label">전원 상태</div><div class="value" id="on">?</div></div>
      <div class="metric"><div class="label">자동제어</div><div class="value" id="auto">?</div></div>
      <div class="metric"><div class="label">목표온도</div><div class="value" id="target">?</div></div>
      <div class="metric"><div class="label">현재온도</div><div class="value" id="temp">?</div></div>
      <div class="metric"><div class="label">켜기 허가</div><div class="value" id="armed">?</div></div>
      <div class="metric"><div class="label">켜기 대기</div><div class="value" id="wait">?</div></div>
      <div class="metric"><div class="label">끄기 대기</div><div class="value" id="onwait">?</div></div>
      <div class="metric"><div class="label">켜기 보호시간</div><div class="value" id="minoff">?</div></div>
      <div class="metric"><div class="label">끄기 보호시간</div><div class="value" id="minon">?</div></div>
      <div class="metric"><div class="label">현재 상태 시간</div><div class="value" id="elapsed">?</div></div>
      <div class="metric"><div class="label">센서 수신</div><div class="value" id="sensorAge">?</div></div>
      <div class="metric"><div class="label">현재습도</div><div class="value" id="humidity">?</div></div>
      <div class="metric"><div class="label">팬</div><div class="value" id="fan">?</div></div>
      <div class="metric"><div class="label">LED</div><div class="value" id="led">?</div></div>
    </section>
    <section class="setpoint">
      <input id="targetInput" type="number" min="0" max="25" step="0.5" value="15.0" aria-label="목표온도">
      <button class="primary" onclick="setTarget(this)">목표온도 적용</button>
    </section>
    <section class="setpoint">
      <input id="ledInput" type="number" min="0" max="100" step="5" value="0" aria-label="LED 출력">
      <button onclick="setPercent('led', this)">LED 출력 적용</button>
    </section>
    <section class="controls">
      <button onclick="send('status', this, '상태 확인')">상태 확인</button>
      <button class="primary" onclick="send('auto 1', this, '자동제어 켜기')">자동제어 켜기</button>
      <button onclick="send('auto 0', this, '자동제어 끄기')">자동제어 끄기</button>
      <button class="primary" onclick="send('arm', this, '켜기 허가')">켜기 허가</button>
      <button onclick="send('on', this, '켜기')">켜기</button>
      <button class="danger" onclick="send('off', this, '끄기')">끄기</button>
      <button onclick="send('disarm', this, '허가 해제')">허가 해제</button>
      <button class="danger" onclick="send('forceoff', this, '비상 끄기')">비상 끄기</button>
      <button onclick="send('fan 100', this, '팬 켜기')">팬 켜기</button>
      <button onclick="send('fan 0', this, '팬 끄기')">팬 끄기</button>
      <button onclick="send('led 100', this, 'LED 100%')">LED 100%</button>
      <button onclick="send('led 0', this, 'LED 0%')">LED 0%</button>
    </section>
    <div class="message" id="message">준비됨</div>
    <pre id="log"></pre>
  </main>
  <script>
    const logEl = document.getElementById('log');
    const messageEl = document.getElementById('message');
    const logs = [];
    const MAX_LOGS = 24;
    let commandInFlight = false;
    let statusInFlight = false;
    let waitRemaining = null;
    let onWaitRemaining = null;
    let stateElapsed = null;
    let stateIsOn = false;

    function appendLog(text) {
      const now = new Date().toLocaleTimeString();
      logs.unshift(`[${now}] ${text}`);
      if (logs.length > MAX_LOGS) logs.length = MAX_LOGS;
      logEl.textContent = logs.join('\\n\\n');
    }

    function setMessage(text, type = '') {
      messageEl.textContent = text;
      messageEl.className = `message ${type}`;
    }

    function setValue(id, text, className = '') {
      const el = document.getElementById(id);
      el.textContent = text;
      el.className = `value ${className}`;
    }

    function parseStatus(line) {
      if (!line.startsWith('STATUS ')) return;
      const data = {};
      for (const part of line.slice(7).trim().split(/\\s+/)) {
        const [key, value] = part.split('=');
        data[key] = value;
      }
      setValue('on', data.on === '1' ? '켜짐' : '꺼짐', data.on === '1' ? 'on' : 'off');
      stateIsOn = data.on === '1';
      setValue('auto', data.auto === '1' ? '켜짐' : '꺼짐', data.auto === '1' ? 'on' : 'off');
      setValue('target', data.target_c && data.target_c !== 'na' ? `${data.target_c}°C` : '없음');
      if (data.target_c && data.target_c !== 'na') document.getElementById('targetInput').value = data.target_c;
      setValue('temp', data.temp_c && data.temp_c !== 'na' ? `${data.temp_c}°C` : '없음', data.temp_c === 'na' ? 'warn' : '');
      setValue('armed', data.armed === '1' ? '허가됨' : '잠김', data.armed === '1' ? 'warn' : 'off');
      waitRemaining = Number.parseInt(data.wait_on_s || '0', 10);
      onWaitRemaining = Number.parseInt(data.wait_off_s || '0', 10);
      stateElapsed = Number.parseInt(data.state_elapsed_s || '0', 10);
      renderWait();
      setValue('minoff', `${data.min_off_s || '?'}s`);
      setValue('minon', `${data.min_on_s || '?'}s`);
      setValue('sensorAge', data.sensor_age_s && data.sensor_age_s !== '-1' ? `${data.sensor_age_s}s 전` : '없음', data.sensor_age_s === '-1' ? 'warn' : '');
      setValue('humidity', data.humidity && data.humidity !== 'na' ? `${data.humidity}%` : '없음', data.humidity === 'na' ? 'warn' : '');
      const fanPct = Number.parseInt(data.fan || '0', 10);
      const ledPct = Number.parseInt(data.led || '0', 10);
      setValue('fan', fanPct > 0 ? '켜짐' : '꺼짐', fanPct > 0 ? 'on' : 'off');
      setValue('led', `${ledPct}%`, ledPct > 0 ? 'on' : 'off');
      if (!Number.isNaN(ledPct)) document.getElementById('ledInput').value = ledPct;
    }

    function renderWait() {
      if (waitRemaining === null || Number.isNaN(waitRemaining)) {
        setValue('wait', '?s');
        return;
      }
      setValue('wait', `${waitRemaining}s`, waitRemaining === 0 ? 'off' : 'warn');
      if (onWaitRemaining === null || Number.isNaN(onWaitRemaining)) {
        setValue('onwait', '?s');
      } else {
        setValue('onwait', `${onWaitRemaining}s`, onWaitRemaining === 0 ? 'off' : 'warn');
      }
      if (stateElapsed === null || Number.isNaN(stateElapsed)) {
        setValue('elapsed', '?');
      } else {
        setValue('elapsed', formatDuration(stateElapsed), stateIsOn ? 'on' : 'off');
      }
    }

    function tickLocalWait() {
      if (waitRemaining !== null && waitRemaining > 0) waitRemaining -= 1;
      if (onWaitRemaining !== null && onWaitRemaining > 0) onWaitRemaining -= 1;
      if (stateElapsed !== null) stateElapsed += 1;
      renderWait();
    }

    function formatDuration(seconds) {
      const s = Math.max(0, Number.parseInt(seconds || 0, 10));
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      const sec = s % 60;
      if (h > 0) return `${h}h ${m}m`;
      if (m > 0) return `${m}m ${sec}s`;
      return `${sec}s`;
    }

    async function send(command, button = null, label = command, quiet = false) {
      if (quiet && (statusInFlight || commandInFlight)) return;
      if (!quiet && commandInFlight) {
        setMessage('명령 처리 중...', '');
        return;
      }
      if (quiet) {
        statusInFlight = true;
      } else {
        commandInFlight = true;
      }
      if (button) {
        button.classList.add('busy');
        button.disabled = true;
      }
      if (!quiet) setMessage(`${label} 보내는 중...`, '');
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2500);
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command }),
          signal: controller.signal
        });
        const data = await res.json();
        if (!quiet) appendLog(`> ${label}\\n${data.output || data.error || ''}`);
        if (data.status) parseStatus(data.status);
        if (!quiet) setMessage(data.error ? data.error : `${label} 완료`, data.error ? 'err' : 'ok');
      } catch (err) {
        if (!quiet) {
          appendLog(`ERR ${err}`);
          setMessage(`실패: ${err}`, 'err');
        }
      } finally {
        clearTimeout(timeout);
        if (button) {
          button.classList.remove('busy');
          button.disabled = false;
        }
        if (quiet) {
          statusInFlight = false;
        } else {
          commandInFlight = false;
        }
      }
    }

    function setTarget(button) {
      const raw = document.getElementById('targetInput').value;
      const value = Math.min(25, Math.max(0, Number.parseFloat(raw || '0')));
      document.getElementById('targetInput').value = value.toFixed(1);
      send(`target ${value.toFixed(1)}`, button, '목표온도 적용');
    }

    function setPercent(name, button) {
      const input = document.getElementById(`${name}Input`);
      const value = Math.min(100, Math.max(0, Number.parseInt(input.value || '0', 10)));
      input.value = value;
      send(`${name} ${value}`, button, `${name.toUpperCase()} ${value}%`);
    }

    send('status', null, '상태 확인');
    setInterval(tickLocalWait, 1000);
    setInterval(() => send('status', null, '온도 갱신', true), 2000);
  </script>
</body>
</html>
"""


def find_port():
    ports = list(serial.tools.list_ports.comports())
    candidates = [
        port.device
        for port in ports
        if "usbmodem" in port.device.lower() or "usbserial" in port.device.lower()
    ]
    return candidates[0] if candidates else None


class SerialBridge:
    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.lock = threading.Lock()
        self.lines = []
        self.last_status = None
        self.running = True
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.reader.start()

    def _read_loop(self):
        while self.running:
            try:
                line = self.ser.readline()
            except serial.SerialException:
                time.sleep(0.1)
                continue
            if not line:
                continue
            text = line.decode("utf-8", "replace").strip()
            if not text:
                continue
            with self.lock:
                self.lines.append(text)
                if len(self.lines) > 80:
                    self.lines = self.lines[-80:]
                if text.startswith("STATUS "):
                    self.last_status = text

    def command(self, command, timeout=0.9):
        with self.lock:
            start_index = len(self.lines)
            previous_status = self.last_status
        with self.lock:
            self.ser.write((command + "\n").encode("utf-8"))

        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                new_lines = self.lines[start_index:]
                if command == "status" and self.last_status != previous_status:
                    return new_lines, self.last_status
                if command != "status" and any(line.startswith(("OK", "ERR")) for line in new_lines):
                    break
            time.sleep(0.02)

        if command != "status":
            with self.lock:
                start_index = len(self.lines)
            with self.lock:
                self.ser.write(b"status\n")
            deadline = time.time() + timeout
            while time.time() < deadline:
                with self.lock:
                    new_lines = self.lines[start_index:]
                    if any(line.startswith("STATUS ") for line in new_lines):
                        return self.lines[start_index:], self.last_status
                time.sleep(0.02)

        with self.lock:
            return self.lines[start_index:], self.last_status


def send_command(command):
    command = command.strip().lower()
    parts = command.split()
    if not parts:
        return {"error": "empty command"}
    if parts[0] not in COMMANDS and parts[0] not in {"pulse", "minoff", "minon"}:
        return {"error": "command not allowed"}

    lines, status = BRIDGE.command(command)
    result = {"output": "\n".join(lines), "status": status}
    if not lines and status is None:
        result["error"] = "Pico 응답 없음"
    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path != "/":
            self.send_response(404)
            self.end_headers()
            return
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/command":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        result = send_command(str(payload.get("command", "")))
        body = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main():
    global SERIAL_PORT, BAUD, BRIDGE

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=None)
    parser.add_argument("--baud", default=115200, type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--web-port", default=8765, type=int)
    args = parser.parse_args()

    SERIAL_PORT = args.port or find_port()
    BAUD = args.baud
    if not SERIAL_PORT:
        raise SystemExit("No Pico/XIAO serial port found. Pass --port /dev/cu.usbmodemXXXX")

    BRIDGE = SerialBridge(SERIAL_PORT, BAUD)
    time.sleep(0.2)
    BRIDGE.command("status")

    server = ThreadingHTTPServer((args.host, args.web_port), Handler)
    print("Serial:", SERIAL_PORT)
    print("Open: http://{}:{}".format(args.host, args.web_port))
    server.serve_forever()


if __name__ == "__main__":
    main()
