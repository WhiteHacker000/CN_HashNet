# Backend Service A (Mac 3)

## 📌 Overview
Backend Instance A runs on **Mac 3** (`10.7.9.142`) on port `3001`. It is built using Python's built-in `http.server` standard library with zero third-party dependencies.

The service binds to `0.0.0.0:3001` (LAN accessible) to accept upstream reverse proxy connections from Mac 2 (`10.7.28.232`).

---

## ⚙️ Specifications

- **Host Machine**: Mac 3
- **LAN IP**: `10.7.9.142`
- **Listening Port**: `3001` (Socket: `0.0.0.0:3001`)
- **Custom Header**: `X-Backend: Backend-A`
- **Caching Header**: `Cache-Control: max-age=60`

---

## 🛣️ API Endpoints

### 1. `GET /`
Returns a JSON greeting and server instance identification:
```json
{
    "message": "Hello from Backend A",
    "backend": "A",
    "server_ip": "10.7.9.142",
    "port": 3001
}
```

### 2. `GET /api/status`
Returns health check status and backend instance information:
```json
{
    "status": "ok",
    "backend": "A",
    "server_ip": "10.7.9.142",
    "port": 3001
}
```

---

## 🚀 How to Run

```bash
cd backend-a
python3 server.py
```

---

## 🧪 Verification via curl

Direct request against Backend A:
```bash
curl -i http://10.7.9.142:3001/api/status
```

Expected HTTP Headers:
```http
HTTP/1.0 200 OK
Server: BaseHTTP/0.6 Python/3.12.x
Date: <timestamp>
Content-Type: application/json
Content-Length: 73
Cache-Control: max-age=60
X-Backend: Backend-A
```
