from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class BackendAHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=4).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("X-Backend", "Backend-A")
        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.send_json({
                "message": "Hello from Backend A",
                "backend": "A",
                "server_ip": "10.7.9.142",
                "port": 3001
            })

        elif self.path == "/api/status":
            self.send_json({
                "status": "ok",
                "backend": "A",
                "server_ip": "10.7.9.142",
                "port": 3001
            })

        else:
            self.send_json({
                "error": "Not Found"
            }, 404)

    def log_message(self, format, *args):
        print(
            f"[Backend-A] "
            f"{self.address_string()} - "
            f"{format % args}"
        )


if __name__ == "__main__":
    # Bound to 0.0.0.0 (LAN-accessible, NOT 127.0.0.1)
    server = HTTPServer(
        ("0.0.0.0", 3001),
        BackendAHandler
    )

    print("Backend A running on 0.0.0.0:3001")
    print("Server IP: 10.7.9.142")

    server.serve_forever()
