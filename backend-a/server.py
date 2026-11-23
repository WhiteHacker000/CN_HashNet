#!/usr/bin/env python3
"""
Backend A — Team 1 Private Network Service Platform (Mac 3, port 3001)

Phase 1 endpoints (unchanged behaviour):
  GET /              -> hello JSON
  GET /api/status    -> {"status": "ok", "backend": "A", ...}

Phase 2 additions:
  GET /health        -> lightweight liveness check (never cached)
  GET /api/data      -> identical JSON on BOTH backends, with an ETag, so a
                        conditional request (If-None-Match) returns 304 Not
                        Modified no matter which backend nginx picks
  HEAD <any path>    -> same headers as GET, no body (so `curl -I` works;
                        Python's http.server answers 501 to HEAD otherwise)

Run:  python3 backend-a/server.py
Env overrides (optional): PORT, BIND, SERVER_IP
"""
import hashlib
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BACKEND_ID = "A"
PORT = int(os.environ.get("PORT", "3001"))
BIND = os.environ.get("BIND", "0.0.0.0")          # LAN-accessible, NOT 127.0.0.1
SERVER_IP = os.environ.get("SERVER_IP", "10.7.9.142")
STARTED_AT = time.time()

# This payload MUST be byte-identical on Backend A and Backend B.
# The ETag is a hash of the body, so both backends compute the same ETag and a
# client's If-None-Match is valid whichever backend the load balancer chooses.
SHARED_DATA = {
    "service": "team1-private-network-platform",
    "dataset": "phase2-cache-demo",
    "version": 2,
    "items": ["dns", "tcp", "tls", "http", "load-balancing", "caching"],
}
SHARED_BODY = json.dumps(SHARED_DATA, indent=4, sort_keys=True).encode("utf-8")
SHARED_ETAG = '"' + hashlib.sha256(SHARED_BODY).hexdigest()[:16] + '"'


def etag_matches(header_value, etag):
    """True if an If-None-Match header value matches our ETag (handles *, lists, W/)."""
    if not header_value:
        return False
    for candidate in header_value.split(","):
        candidate = candidate.strip()
        if candidate == "*":
            return True
        if candidate.startswith("W/"):
            candidate = candidate[2:]
        if candidate == etag:
            return True
    return False


class BackendHandler(BaseHTTPRequestHandler):
    server_version = "Team1Backend/2.0"

    def _send(self, status, body=b"", headers=None, head_only=False):
        self.send_response(status)
        self.send_header("X-Backend", "Backend-" + BACKEND_ID)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        if status != 304:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body and not head_only and status != 304:
            self.wfile.write(body)

    def _json(self, data, status=200, cache="max-age=60", head_only=False):
        body = json.dumps(data, indent=4).encode("utf-8")
        self._send(status, body, {"Cache-Control": cache}, head_only)

    def _route(self, head_only=False):
        path = self.path.split("?", 1)[0]

        if path == "/":
            self._json({
                "message": "Hello from Backend " + BACKEND_ID,
                "backend": BACKEND_ID,
                "server_ip": SERVER_IP,
                "port": PORT,
            }, head_only=head_only)

        elif path == "/api/status":
            self._json({
                "status": "ok",
                "backend": BACKEND_ID,
                "server_ip": SERVER_IP,
                "port": PORT,
            }, head_only=head_only)

        elif path == "/health":
            self._json({
                "status": "healthy",
                "backend": BACKEND_ID,
                "uptime_seconds": round(time.time() - STARTED_AT, 1),
            }, cache="no-store", head_only=head_only)

        elif path == "/api/data":
            headers = {"Cache-Control": "max-age=60", "ETag": SHARED_ETAG}
            if etag_matches(self.headers.get("If-None-Match"), SHARED_ETAG):
                self._send(304, headers=headers)
            else:
                self._send(200, SHARED_BODY, headers, head_only)

        else:
            self._json({"error": "Not Found", "path": path}, 404,
                       cache="no-store", head_only=head_only)

    def do_GET(self):
        self._route()

    def do_HEAD(self):
        self._route(head_only=True)

    def log_message(self, fmt, *args):
        # Show the real client (X-Forwarded-For from nginx) next to the TCP peer
        # (which is always the edge when going through the load balancer).
        xff = self.headers.get("X-Forwarded-For", "-") if hasattr(self, "headers") else "-"
        print("[Backend-%s] peer=%s xff=%s - %s"
              % (BACKEND_ID, self.client_address[0], xff, fmt % args), flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer((BIND, PORT), BackendHandler)
    print("Backend %s running on %s:%d (LAN IP %s)" % (BACKEND_ID, BIND, PORT, SERVER_IP), flush=True)
    print("Data ETag: %s" % SHARED_ETAG, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBackend %s stopped" % BACKEND_ID)
