from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            print("\n[수신]", json.dumps(data, ensure_ascii=False, indent=2))
        except:
            print("\n[수신 RAW]", body.decode(errors='ignore'))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, format, *args):
        pass

print("HTTP 수신 서버 시작 - 192.168.0.30:8080")
HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
