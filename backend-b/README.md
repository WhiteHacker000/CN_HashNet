# Backend Service B (Mac 4)

## 📌 Overview
Backend Instance B runs on **Mac 4** (`10.7.22.224`) on port `3002`. It is built using Python's built-in `http.server` standard library with zero external dependencies.

The service binds to `0.0.0.0:3002` (LAN accessible) to accept upstream reverse proxy connections from Mac 2 (`10.7.28.232`).

---

## ⚙️ Specifications

- **Host Machine**: Mac 4
- **LAN IP**: `10.7.22.224`
- **Listening Port**: `3002` (Socket: `0.0.0.0:3002`)
- **Custom Header**: `X-Backend: Backend-B`
- **Caching Header**: `Cache-Control: max-age=60`

---

## 🛣️ API Endpoints

### 1. `GET /`
Returns a JSON greeting and server instance identification:
```json
{
    "message": "Hello from Backend B",
    "backend": "B",
    "server_ip": "10.7.22.224",
    "port": 3002
}
```

### 2. `GET /api/status`
Returns health check status and backend instance information:
```json
{
    "status": "ok",
    "backend": "B",
    "server_ip": "10.7.22.224",
    "port": 3002
}
```

---

## 🚀 How to Run

```bash
cd backend-b
python3 server.py
```

---

## 🧪 Verification via curl

Direct request against Backend B:
```bash
curl -i http://10.7.22.224:3002/api/status
```

Expected HTTP Headers:
```http
HTTP/1.0 200 OK
Server: BaseHTTP/0.6 Python/3.12.x
Date: <timestamp>
Content-Type: application/json
Content-Length: 73
Cache-Control: max-age=60
X-Backend: Backend-B
```
