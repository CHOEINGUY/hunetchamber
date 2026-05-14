#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
from decimal import Decimal
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import threading
import traceback

import pymysql

STATIC_DIR = Path(__file__).parent / "static"


DB_HOST = os.getenv("HUNET_DB_HOST", "49.247.214.116")
DB_PORT = int(os.getenv("HUNET_DB_PORT", "3306"))
DB_USER = os.getenv("HUNET_DB_USER", "smart_chamber")
DB_PASSWORD = os.getenv("HUNET_DB_PASSWORD", "smart_chamber")
DB_NAME = os.getenv("HUNET_DB_NAME", "smart_chamber")

DEVICE_ID = os.getenv("FRIDGE_DEVICE_ID", "fridge-01")
HTTP_HOST = os.getenv("FRIDGE_HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("FRIDGE_HTTP_PORT", "8081"))

_cmd_lock = threading.Lock()
_pending_cmd = None


def set_pending_cmd(cmd):
    global _pending_cmd
    with _cmd_lock:
        _pending_cmd = cmd


def take_pending_cmd():
    global _pending_cmd
    with _cmd_lock:
        cmd = _pending_cmd
        _pending_cmd = None
        return cmd


INSERT_SQL = """
INSERT INTO fridge_readings (
    device_id,
    temp_c,
    humidity,
    target_c,
    band_c,
    band_low_c,
    fridge_on,
    armed,
    auto_mode,
    fan_percent,
    led_percent,
    min_off_s,
    wait_on_s,
    min_on_s,
    wait_off_s,
    state_elapsed_s,
    sensor_age_s,
    reason,
    raw_json
) VALUES (
    %(device_id)s,
    %(temp_c)s,
    %(humidity)s,
    %(target_c)s,
    %(band_c)s,
    %(band_low_c)s,
    %(fridge_on)s,
    %(armed)s,
    %(auto_mode)s,
    %(fan_percent)s,
    %(led_percent)s,
    %(min_off_s)s,
    %(wait_on_s)s,
    %(min_on_s)s,
    %(wait_off_s)s,
    %(state_elapsed_s)s,
    %(sensor_age_s)s,
    %(reason)s,
    %(raw_json)s
)
"""

READINGS_SQL = """
SELECT
    id,
    created_at,
    TIMESTAMPDIFF(SECOND, created_at, NOW()) AS row_age_s,
    device_id,
    temp_c,
    humidity,
    target_c,
    band_c,
    band_low_c,
    fridge_on,
    armed,
    auto_mode,
    fan_percent,
    led_percent,
    wait_on_s,
    wait_off_s,
    state_elapsed_s,
    sensor_age_s,
    reason
FROM fridge_readings
ORDER BY id DESC
LIMIT %s
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


def value_or_none(data, key):
    value = data.get(key)
    if value in (None, "", "na"):
        return None
    return value


def int_or_none(data, key):
    value = value_or_none(data, key)
    if value is None:
        return None
    return int(value)


def insert_fridge_reading(data):
    payload = {
        "device_id": str(data.get("device_id") or DEVICE_ID),
        "temp_c": value_or_none(data, "temp_c"),
        "humidity": value_or_none(data, "humidity"),
        "target_c": value_or_none(data, "target_c"),
        "band_c": value_or_none(data, "band_c"),
        "band_low_c": value_or_none(data, "band_low_c"),
        "fridge_on": int_or_none(data, "fridge_on"),
        "armed": int_or_none(data, "armed"),
        "auto_mode": int_or_none(data, "auto_mode"),
        "fan_percent": int_or_none(data, "fan_percent"),
        "led_percent": int_or_none(data, "led_percent"),
        "min_off_s": int_or_none(data, "min_off_s"),
        "wait_on_s": int_or_none(data, "wait_on_s"),
        "min_on_s": int_or_none(data, "min_on_s"),
        "wait_off_s": int_or_none(data, "wait_off_s"),
        "state_elapsed_s": int_or_none(data, "state_elapsed_s"),
        "sensor_age_s": int_or_none(data, "sensor_age_s"),
        "reason": str(data.get("reason") or "")[:80],
        "raw_json": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    }

    conn = db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(INSERT_SQL, payload)
            return cur.lastrowid
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


def fetch_readings(limit=50, since_s=None):
    limit = max(1, min(int(limit), 100000))
    conn = db_connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS count FROM fridge_readings")
            count = cur.fetchone()["count"]
            if since_s is None:
                cur.execute(READINGS_SQL, (limit,))
            else:
                since_s = max(1, min(int(since_s), 86400 * 7))
                cur.execute("""
                    SELECT
                        id,
                        created_at,
                        TIMESTAMPDIFF(SECOND, created_at, NOW()) AS row_age_s,
                        device_id,
                        temp_c,
                        humidity,
                        target_c,
                        band_c,
                        band_low_c,
                        fridge_on,
                        armed,
                        auto_mode,
                        fan_percent,
                        led_percent,
                        wait_on_s,
                        wait_off_s,
                        state_elapsed_s,
                        sensor_age_s,
                        reason
                    FROM fridge_readings
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s SECOND)
                    ORDER BY id DESC
                    LIMIT %s
                """, (since_s, limit))
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
        if parsed.path in ("/", "/index.html"):
            self.send_static("index.html")
            return
        if parsed.path == "/health":
            self.send_json(200, {"ok": True, "service": "fridge-gateway"})
            return
        if parsed.path == "/api/readings":
            query = parse_qs(parsed.query)
            limit = query.get("limit", ["50"])[0]
            since_s = query.get("since_s", [None])[0]
            try:
                count, rows = fetch_readings(limit, since_s)
            except Exception as exc:
                print("[DB SELECT ERROR]", repr(exc))
                traceback.print_exc()
                self.send_json(500, {"ok": False, "error": "db_select_failed"})
                return
            self.send_json(200, {"ok": True, "count": count, "rows": rows})
            return
        rel = parsed.path.lstrip("/")
        if rel:
            self.send_static(rel)
            return
        self.send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path == "/api/cmd":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                cmd = str(data.get("cmd", "")).strip()
                if not cmd:
                    raise ValueError("empty cmd")
            except Exception as exc:
                self.send_json(400, {"ok": False, "error": str(exc)})
                return
            set_pending_cmd(cmd)
            print("[CMD QUEUED] {}".format(cmd))
            self.send_json(200, {"ok": True, "cmd": cmd})
            return

        if self.path != "/fridge":
            self.send_json(404, {"ok": False, "error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object")
        except Exception as exc:
            print("[BAD JSON]", body.decode(errors="ignore"))
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        try:
            inserted_id = insert_fridge_reading(data)
        except Exception as exc:
            print("[DB INSERT ERROR]", repr(exc))
            traceback.print_exc()
            self.send_json(500, {"ok": False, "error": "db_insert_failed"})
            return

        cmd = take_pending_cmd()
        response = {"ok": True, "id": inserted_id}
        if cmd:
            response["cmd"] = cmd
            print("[CMD DISPATCH] id={} cmd={}".format(inserted_id, cmd))
        else:
            print("[FRIDGE INSERT] id={} {}".format(inserted_id, json.dumps(data, ensure_ascii=False, sort_keys=True)))
        self.send_json(200, response)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, filename):
        filepath = STATIC_DIR / filename
        try:
            body = filepath.read_bytes()
        except FileNotFoundError:
            self.send_json(404, {"ok": False, "error": "not_found"})
            return
        mime, _ = mimetypes.guess_type(str(filepath))
        content_type = (mime or "application/octet-stream")
        if mime in ("text/html", "text/css", "application/javascript"):
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    print("Hunet fridge gateway")
    print("HTTP: {}:{}".format(HTTP_HOST, HTTP_PORT))
    print("DB: {}:{}/{} user={}".format(DB_HOST, DB_PORT, DB_NAME, DB_USER))
    print("Endpoint: POST /fridge")
    print("Dashboard: http://127.0.0.1:{}/".format(HTTP_PORT))
    ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
