# Edge Reverse Proxy & Load Balancer Subsystem (Mac 2)

## 📌 Overview
**Mac 2** (`10.7.28.232`) serves as the edge gateway for all incoming client traffic. It fulfills three critical networking roles:
1. **Reverse Proxy Entry Point**: Clients connect only to Mac 2 on ports `8080` (HTTP) and `8443` (HTTPS); backend IPs remain isolated from client knowledge.
2. **TLS Termination**: Performs SSL/TLS handshake and decrypts client HTTPS traffic before proxying to backends.
3. **Upstream Load Balancer**: Distributes incoming requests between Backend A (`10.7.9.142:3001`) and Backend B (`10.7.22.224:3002`) using round-robin distribution.

---

## ⚙️ Architecture & Upstream Configuration

```nginx
upstream team1_backends {
    server 10.7.9.142:3001;   # Backend A (Mac 3)
    server 10.7.22.224:3002;  # Backend B (Mac 4)
}
```

- **HTTP Port**: `8080`
- **HTTPS Port**: `8443` (with SSL/TLS termination)
- **Domain Names**: `app.team1.test`, `api.team1.test`

---

## 🛡️ Forwarded Headers & Protocol Integrity
To preserve the client's original network context when passing requests to the backends, Nginx attaches the following headers:
- `Host: $host`
- `X-Real-IP: $remote_addr`
- `X-Forwarded-For: $proxy_add_x_forwarded_for`
- `X-Forwarded-Proto: $scheme`

Furthermore, Nginx passes through the upstream headers:
- `X-Backend` (identifying which backend answered)
- `Cache-Control` (instructing client caching behavior)

---

## 🚀 How to Run Nginx on Mac 2

1. **Test Nginx configuration syntax**:
   ```bash
   sudo nginx -t -c /path/to/nginx.conf
   ```

2. **Start / Reload Nginx**:
   ```bash
   sudo nginx -c /path/to/nginx.conf
   # To reload configuration:
   sudo nginx -s reload
   ```

---

## 🔒 Security Notice
In accordance with security best practices, private TLS key files (`*.key`, `*.pem`) are strictly excluded from version control. The `team1.conf` in this repository uses sanitized path placeholders.
