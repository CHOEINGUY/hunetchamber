import serial
import serial.tools.list_ports
import time
import threading
import re
from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Hunet Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg: #0b0f19;
            --card-bg: rgba(30, 41, 59, 0.7);
            --text: #f1f5f9;
            --text-dim: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, sans-serif;
            background: radial-gradient(circle at top right, #1e293b, #0b0f19);
            color: var(--text);
            padding: 24px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        h1 { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.03em; }
        .status-badge {
            display: flex; align-items: center; gap: 8px;
            padding: 6px 16px; border-radius: 50px;
            background: #1e293b; border: 1px solid #334155;
            font-size: 0.8rem; font-weight: 600;
        }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: #64748b; }
        .online .dot { background: #10b981; box-shadow: 0 0 8px #10b981; }

        .section-label {
            font-size: 0.75rem; font-weight: 600; letter-spacing: 0.1em;
            color: var(--text-dim); text-transform: uppercase;
            padding: 4px 0;
            border-bottom: 1px solid #1e293b;
        }

        .grid-3 {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }
        .grid-2 {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            transition: transform 0.2s;
        }
        .card:hover { transform: translateY(-3px); }
        .card-label { font-size: 0.8rem; color: var(--text-dim); font-weight: 500; }
        .card-value {
            font-size: 2.4rem; font-weight: 800;
            display: flex; align-items: baseline; gap: 4px;
        }
        .card-unit { font-size: 1rem; color: var(--text-dim); font-weight: 400; }

        .c-airtemp   { color: #fb923c; }
        .c-humidity  { color: #38bdf8; }
        .c-moisture  { color: #34d399; }
        .c-soiltemp  { color: #fbbf24; }
        .c-ec        { color: #a78bfa; }
        .c-ph        { color: #f472b6; }
        .c-n         { color: #4ade80; }
        .c-p         { color: #f87171; }
        .c-k         { color: #60a5fa; }

        .chart-box {
            background: var(--card-bg);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            padding: 20px 24px;
            height: 260px;
        }
        .log-panel {
            background: rgba(0,0,0,0.35);
            border-radius: 14px;
            padding: 12px 16px;
            font-family: monospace;
            font-size: 0.82rem;
            height: 100px;
            overflow-y: auto;
            border: 1px solid #1e293b;
            color: #64748b;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Hunet Sensor Dashboard</h1>
        <div id="badge" class="status-badge">
            <div class="dot"></div>
            <span id="status-text">DISCONNECTED</span>
        </div>
    </div>

    <div class="section-label">공기 (온습도 센서)</div>
    <div class="grid-2">
        <div class="card">
            <div class="card-label">Air Temperature</div>
            <div class="card-value c-airtemp"><span id="v-airtemp">--.-</span><span class="card-unit">°C</span></div>
        </div>
        <div class="card">
            <div class="card-label">Humidity</div>
            <div class="card-value c-humidity"><span id="v-humidity">--.-</span><span class="card-unit">%</span></div>
        </div>
    </div>

    <div class="section-label">토양 (5 in 1 센서)</div>
    <div class="grid-3">
        <div class="card">
            <div class="card-label">Soil Moisture</div>
            <div class="card-value c-moisture"><span id="v-moisture">--.-</span><span class="card-unit">%</span></div>
        </div>
        <div class="card">
            <div class="card-label">Soil Temperature</div>
            <div class="card-value c-soiltemp"><span id="v-soiltemp">--.-</span><span class="card-unit">°C</span></div>
        </div>
        <div class="card">
            <div class="card-label">EC</div>
            <div class="card-value c-ec"><span id="v-ec">---</span><span class="card-unit">µS/cm</span></div>
        </div>
        <div class="card">
            <div class="card-label">pH</div>
            <div class="card-value c-ph"><span id="v-ph">--.-</span></div>
        </div>
        <div class="card">
            <div class="card-label">Nitrogen (N)</div>
            <div class="card-value c-n"><span id="v-n">---</span><span class="card-unit">mg/kg</span></div>
        </div>
        <div class="card">
            <div class="card-label">Phosphorus (P)</div>
            <div class="card-value c-p"><span id="v-p">---</span><span class="card-unit">mg/kg</span></div>
        </div>
    </div>
    <div class="grid-3">
        <div class="card">
            <div class="card-label">Potassium (K)</div>
            <div class="card-value c-k"><span id="v-k">---</span><span class="card-unit">mg/kg</span></div>
        </div>
        <div class="chart-box" style="grid-column: span 2;">
            <canvas id="chart"></canvas>
        </div>
    </div>

    <div class="section-label">광량 (조도 센서)</div>
    <div class="grid-3">
        <div class="card">
            <div class="card-label">Solar Radiation</div>
            <div class="card-value" style="color:#facc15;"><span id="v-solar">---</span><span class="card-unit">W/m²</span></div>
        </div>
    </div>

    <div class="section-label">CO2 (이산화탄소 센서)</div>
    <div class="grid-3">
        <div class="card">
            <div class="card-label">CO2</div>
            <div class="card-value" style="color:#6ee7b7;"><span id="v-co2">---</span><span class="card-unit">ppm</span></div>
        </div>
    </div>

    <div class="section-label">제어</div>
    <div class="grid-3">
        <div class="card" style="flex-direction:row; align-items:center; justify-content:space-between;">
            <div>
                <div class="card-label">팬 (릴레이)</div>
                <div id="relay-status" style="font-size:1rem; font-weight:700; color:#64748b; margin-top:4px;">OFF</div>
            </div>
        </div>
    </div>

    <div id="log" class="log-panel"><div>Initializing...</div></div>

    <script>
        const socket = io();
        const badge = document.getElementById('badge');
        const ctx = document.getElementById('chart').getContext('2d');

        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'AirTemp(°C)', borderColor: '#fb923c', data: [], borderWidth: 2, tension: 0.4, pointRadius: 0, yAxisID: 'y' },
                    { label: 'Humidity(%)', borderColor: '#38bdf8', data: [], borderWidth: 2, tension: 0.4, pointRadius: 0, yAxisID: 'y2' },
                    { label: 'Moisture(%)', borderColor: '#34d399', data: [], borderWidth: 2, tension: 0.4, pointRadius: 0, yAxisID: 'y2' },
                    { label: 'SoilTemp(°C)', borderColor: '#fbbf24', data: [], borderWidth: 2, tension: 0.4, pointRadius: 0, yAxisID: 'y' },
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { display: false },
                    y:  { type: 'linear', position: 'left',  ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y2: { type: 'linear', position: 'right', ticks: { color: '#94a3b8' }, grid: { display: false }, min: 0, max: 100 }
                },
                plugins: { legend: { labels: { color: '#94a3b8', boxWidth: 12, font: { size: 11 } } } }
            }
        });

        socket.on('connect',    () => { badge.className = 'status-badge online'; document.getElementById('status-text').innerText = 'ONLINE'; });
        socket.on('disconnect', () => { badge.className = 'status-badge';        document.getElementById('status-text').innerText = 'DISCONNECTED'; });


        socket.on('sensor_update', (d) => {
            document.getElementById('v-airtemp').innerText  = d.air_temp;
            document.getElementById('v-humidity').innerText = d.humidity;
            document.getElementById('v-moisture').innerText = d.moisture;
            document.getElementById('v-soiltemp').innerText = d.soil_temp;
            document.getElementById('v-ec').innerText       = d.ec;
            document.getElementById('v-ph').innerText       = d.ph;
            document.getElementById('v-n').innerText        = d.n;
            document.getElementById('v-p').innerText        = d.p;
            document.getElementById('v-k').innerText        = d.k;
            document.getElementById('v-solar').innerText    = d.solar;
            document.getElementById('v-co2').innerText      = d.co2;

            relayOn = d.relay === 1;
            document.getElementById('relay-status').innerText = relayOn ? 'ON' : 'OFF';
            document.getElementById('relay-status').style.color = relayOn ? '#10b981' : '#64748b';
            document.getElementById('relay-btn').innerText = relayOn ? '끄기' : '켜기';
            document.getElementById('relay-btn').style.background = relayOn ? '#10b981' : '#1e293b';

            const now = new Date().toLocaleTimeString();
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(d.air_temp);
            chart.data.datasets[1].data.push(d.humidity);
            chart.data.datasets[2].data.push(d.moisture);
            chart.data.datasets[3].data.push(d.soil_temp);
            if (chart.data.labels.length > 30) {
                chart.data.labels.shift();
                chart.data.datasets.forEach(ds => ds.data.shift());
            }
            chart.update('none');

            const log = document.getElementById('log');
            const entry = document.createElement('div');
            entry.innerText = `[${now}] Air:${d.air_temp}°C ${d.humidity}% | Soil:${d.moisture}% ${d.soil_temp}°C EC:${d.ec} pH:${d.ph}`;
            log.prepend(entry);
            if (log.childElementCount > 6) log.removeChild(log.lastChild);
        });
    </script>
</body>
</html>
"""

# AirTemp:23.5C | Humidity:36.4% || Moisture:0.0% | SoilTemp:27.2C | EC:0 | pH:9.0 | N:0 P:0 K:0
PATTERN = re.compile(
    r"AirTemp:([\d\.-]+)C \| Humidity:([\d\.-]+)%"
    r" \|\| "
    r"Moisture:([\d\.-]+)% \| SoilTemp:([\d\.-]+)C \| EC:(\d+) \| pH:([\d\.-]+) \| N:(\d+) P:(\d+) K:(\d+)"
    r" \|\| "
    r"Solar:(\d+) W/m2"
    r" \|\| "
    r"CO2:(\d+) ppm"
    r" \|\| "
    r"RELAY:(\d+)"
)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


def find_rp2040_port():
    ports = serial.tools.list_ports.comports()
    candidates = [p.device for p in ports if "usbmodem" in p.device.lower()]
    return candidates[0] if candidates else None

def serial_reader():
    last_port = None
    ser = None
    while True:
        port = find_rp2040_port()
        if port:
            if port != last_port:
                try:
                    if ser: ser.close()
                    ser = serial.Serial(port, 115200, timeout=1)
                    last_port = port
                except:
                    time.sleep(1)
                    continue
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        print(f"[RAW] {line}")
                        m = PATTERN.search(line)
                        if m:
                            socketio.emit('sensor_update', {
                                'air_temp': float(m.group(1)),
                                'humidity': float(m.group(2)),
                                'moisture': float(m.group(3)),
                                'soil_temp': float(m.group(4)),
                                'ec':    int(m.group(5)),
                                'ph':    float(m.group(6)),
                                'n':     int(m.group(7)),
                                'p':     int(m.group(8)),
                                'k':     int(m.group(9)),
                                'solar': int(m.group(10)),
                                'co2':   int(m.group(11)),
                                'relay': int(m.group(12)),
                            })
            except:
                last_port = None
                if ser: ser.close()
        else:
            last_port = None
            if ser: ser.close()
        time.sleep(0.01)

if __name__ == '__main__':
    threading.Thread(target=serial_reader, daemon=True).start()
    print("Dashboard: http://127.0.0.1:5001")
    socketio.run(app, port=5001, debug=False)
