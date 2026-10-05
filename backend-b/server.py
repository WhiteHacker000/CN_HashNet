from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class BackendBHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=4).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("X-Backend", "Backend-B")
        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.send_json({
                "message": "Hello from Backend B",
                "backend": "B",
                "server_ip": "10.7.22.224",
                "port": 3002
            })

        elif self.path == "/api/status":
            self.send_json({
                "status": "ok",
                "backend": "B",
                "server_ip": "10.7.22.224",
                "port": 3002
            })

        else:
            self.send_json({
                "error": "Not Found"
            }, 404)

    def log_message(self, format, *args):
        print(
            f"[Backend-B] "
            f"{self.address_string()} - "
            f"{format % args}"
        )


if __name__ == "__main__":
    # Bound to 0.0.0.0 (LAN-accessible, NOT 127.0.0.1)
    server = HTTPServer(
        ("0.0.0.0", 3002),
        BackendBHandler
    )

    print("Backend B running on 0.0.0.0:3002")
    print("Server IP: 10.7.22.224")

    server.serve_forever()
