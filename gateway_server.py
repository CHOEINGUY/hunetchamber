from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from urllib.parse import parse_qs, urlparse
import traceback

import pymysql


DB_HOST = os.getenv("HUNET_DB_HOST", "49.247.214.116")
DB_PORT = int(os.getenv("HUNET_DB_PORT", "3306"))
DB_USER = os.getenv("HUNET_DB_USER", "smart_chamber")
DB_PASSWORD = os.getenv("HUNET_DB_PASSWORD", "smart_chamber")
DB_NAME = os.getenv("HUNET_DB_NAME", "smart_chamber")
DEVICE_ID = os.getenv("HUNET_DEVICE_ID", "pico-w5500-01")
HTTP_HOST = os.getenv("HUNET_HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("HUNET_HTTP_PORT", "8080"))


INSERT_SQL = """
INSERT INTO sensor_readings (
    device_id,
    air_temp,
    humidity,
    moisture,
    soil_temp,
    ec,
    ph,
    n,
    p,
    k,
    solar,
    co2,
    relay,
    raw_json
) VALUES (
    %(device_id)s,
    %(air_temp)s,
    %(humidity)s,
    %(moisture)s,
    %(soil_temp)s,
    %(ec)s,
    %(ph)s,
    %(n)s,
    %(p)s,
    %(k)s,
    %(solar)s,
    %(co2)s,
    %(relay)s,
    %(raw_json)s
)
"""

READINGS_SQL = """
SELECT
    id,
    created_at,
    device_id,
    air_temp,
    humidity,
    moisture,
    soil_temp,
    ec,
    ph,
    n,
    p,
    k,
    solar,
    co2,
    relay
FROM sensor_readings
ORDER BY id DESC
LIMIT %s
"""

INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hunet Sensor Monitor</title>
  <style>
    :root {
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f7f8;
      color: #172026;
    }
    body { margin: 0; }
    main { max-width: 1180px; margin: 0 auto; padding: 28px 18px 48px; }
    header { display: flex; justify-content: space-between; gap: 18px; align-items: flex-end; margin-bottom: 18px; }
    h1 { font-size: 26px; margin: 0 0 6px; letter-spacing: 0; }
    p { margin: 0; color: #5b6670; }
    .status { text-align: right; font-size: 14px; color: #47525d; }
    .latest {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin: 20px 0;
    }
    .metric {
      background: #fff;
      border: 1px solid #dfe5e8;
      border-radius: 8px;
      padding: 12px 14px;
      min-height: 78px;
    }
    .metric span { display: block; color: #64707b; font-size: 13px; margin-bottom: 8px; }
    .metric strong { font-size: 24px; font-weight: 700; }
    .table-wrap { overflow-x: auto; background: #fff; border: 1px solid #dfe5e8; border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; min-width: 980px; }
    th, td { padding: 10px 12px; border-bottom: 1px solid #edf1f3; text-align: right; font-size: 14px; white-space: nowrap; }
    th { color: #52606b; font-weight: 650; background: #f9fbfc; }
    th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) { text-align: left; }
    tr:last-child td { border-bottom: 0; }
    .empty { padding: 32px; text-align: center; color: #64707b; }
    @media (max-width: 720px) {
      header { display: block; }
      .status { text-align: left; margin-top: 12px; }
      h1 { font-size: 22px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Hunet Sensor Monitor</h1>
        <p>MariaDB에 저장된 최신 센서 데이터를 자동 갱신해서 보여줍니다.</p>
      </div>
      <div class="status">
        <div id="connection">연결 확인 중...</div>
        <div id="updated">-</div>
      </div>
    </header>

    <section class="latest" id="latest"></section>
    <section class="table-wrap" id="table"></section>
  </main>

  <script>
    const labels = [
      ["air_temp", "공기 온도", "°C"],
      ["humidity", "습도", "%"],
      ["moisture", "토양 수분", "%"],
      ["soil_temp", "토양 온도", "°C"],
      ["ph", "pH", ""],
      ["ec", "EC", ""],
      ["solar", "조도", "W/m²"],
      ["co2", "CO₂", "ppm"],
      ["relay", "릴레이", ""]
    ];

    function valueText(value, unit = "") {
      if (value === null || value === undefined) return "-";
      return `${value}${unit ? " " + unit : ""}`;
    }

    function renderLatest(row) {
      const el = document.getElementById("latest");
      if (!row) {
        el.innerHTML = "";
        return;
      }
      el.innerHTML = labels.map(([key, label, unit]) => `
        <div class="metric">
          <span>${label}</span>
          <strong>${valueText(row[key], unit)}</strong>
        </div>
      `).join("");
    }

    function renderTable(rows) {
      const el = document.getElementById("table");
      if (!rows.length) {
        el.innerHTML = '<div class="empty">아직 저장된 데이터가 없습니다.</div>';
        return;
      }
      el.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>ID</th><th>시간</th><th>장치</th><th>공기온도</th><th>습도</th>
              <th>토양수분</th><th>토양온도</th><th>EC</th><th>pH</th>
              <th>N</th><th>P</th><th>K</th><th>조도</th><th>CO₂</th><th>릴레이</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(row => `
              <tr>
                <td>${row.id}</td>
                <td>${row.created_at}</td>
                <td>${row.device_id}</td>
                <td>${valueText(row.air_temp)}</td>
                <td>${valueText(row.humidity)}</td>
                <td>${valueText(row.moisture)}</td>
                <td>${valueText(row.soil_temp)}</td>
                <td>${valueText(row.ec)}</td>
                <td>${valueText(row.ph)}</td>
                <td>${valueText(row.n)}</td>
                <td>${valueText(row.p)}</td>
                <td>${valueText(row.k)}</td>
                <td>${valueText(row.solar)}</td>
                <td>${valueText(row.co2)}</td>
                <td>${valueText(row.relay)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    async function refresh() {
      const connection = document.getElementById("connection");
      const updated = document.getElementById("updated");
      try {
        const res = await fetch("/api/readings?limit=30", { cache: "no-store" });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || "request failed");
        renderLatest(data.rows[0]);
        renderTable(data.rows);
        connection.textContent = `DB rows: ${data.count}`;
        updated.textContent = `화면 갱신: ${new Date().toLocaleTimeString()}`;
      } catch (err) {
        connection.textContent = "연결 실패";
        updated.textContent = err.message;
      }
    }

    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""


def db_connect():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        connect_timeout=8,
        read_timeout=8,
        write_timeout=8,
        autocommit=True,
    )


def number_or_none(data, key):
    value = data.get(key)
    if value is None:
        return None
    if value == "":
        return None
    return value


def insert_sensor_reading(data):
    payload = {
        "device_id": str(data.get("device_id") or DEVICE_ID),
        "air_temp": number_or_none(data, "air_temp"),
        "humidity": number_or_none(data, "humidity"),
        "moisture": number_or_none(data, "moisture"),
        "soil_temp": number_or_none(data, "soil_temp"),
        "ec": number_or_none(data, "ec"),
        "ph": number_or_none(data, "ph"),
        "n": number_or_none(data, "n"),
        "p": number_or_none(data, "p"),
        "k": number_or_none(data, "k"),
        "solar": number_or_none(data, "solar"),
        "co2": number_or_none(data, "co2"),
        "relay": number_or_none(data, "relay"),
        "raw_json": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    }

    conn = db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(INSERT_SQL, payload)
            inserted_id = cur.lastrowid
        return inserted_id
    finally:
        conn.close()


def json_safe(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def fetch_readings(limit=30):
    limit = max(1, min(int(limit), 200))
    conn = db_connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS count FROM sensor_readings")
            count = cur.fetchone()["count"]
            cur.execute(READINGS_SQL, (limit,))
            rows = [
                {key: json_safe(value) for key, value in row.items()}
                for row in cur.fetchall()
            ]
        return count, rows
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_html(200, INDEX_HTML)
            return

        if parsed.path == "/health":
            self.send_json(200, {"ok": True, "service": "hunet-gateway"})
            return

        if parsed.path == "/api/readings":
            query = parse_qs(parsed.query)
            limit = query.get("limit", ["30"])[0]
            try:
                count, rows = fetch_readings(limit)
            except Exception as exc:
                print("[DB ERROR]", repr(exc))
                traceback.print_exc()
                self.send_json(500, {"ok": False, "error": "db_select_failed"})
                return
            self.send_json(200, {"ok": True, "count": count, "rows": rows})
            return

        self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/sensor":
            self.send_json(404, {"ok": False, "error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object")
        except Exception as exc:
            print("\n[BAD JSON]", body.decode(errors="ignore"))
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        received_at = datetime.now(timezone.utc).isoformat()
        print("\n[수신]", json.dumps(data, ensure_ascii=False, sort_keys=True))

        try:
            inserted_id = insert_sensor_reading(data)
        except Exception as exc:
            print("[DB ERROR]", repr(exc))
            traceback.print_exc()
            self.send_json(500, {"ok": False, "error": "db_insert_failed"})
            return

        print("[DB INSERT] id={} at={}".format(inserted_id, received_at))
        self.send_json(200, {"ok": True, "id": inserted_id})

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_html(self, status, html):
        body = html.encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass


def main():
    print("Hunet gateway server")
    print("HTTP: {}:{}".format(HTTP_HOST, HTTP_PORT))
    print("DB: {}:{}/{} user={}".format(DB_HOST, DB_PORT, DB_NAME, DB_USER))
    print("Endpoint: POST /sensor")
    print("Dashboard: http://127.0.0.1:{}/".format(HTTP_PORT))
    ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
