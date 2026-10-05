# Protocol Analysis & Wireshark Evidence Inventory

## 📌 Overview
This directory contains packet captures and protocol verification records for **Team 1 — Private Network Service Platform (Phase 1)**.

Packet analysis was performed across all critical network boundaries:
1. **Application Layer**: DNS queries (`UDP 53`) and HTTP response headers (`Cache-Control`, `X-Backend`)
2. **Session / Security Layer**: TLS 1.2/1.3 cryptographic handshakes and encrypted application data records
3. **Transport Layer**: TCP 3-way handshakes (`SYN` → `SYN-ACK` → `ACK`) and port mappings

---

## 📸 Documented Evidence Artifacts

| Evidence Item | Source / Target | Protocol / Ports | Description & Observed Behavior | Status |
| :--- | :--- | :--- | :--- | :--- |
| **01_DNS_Resolution** | Client (`10.7.28.232`) → DNS (`10.7.21.208`) | UDP Port 53 | DNS Query for `app.team1.test` returning `10.7.28.232` in Answer section | **VERIFIED** |
| **02_TCP_Handshake** | Client (`10.7.28.232`) → Edge (`10.7.28.232:8443`) | TCP Port 8443 | Three-way handshake: Client SYN → Server SYN, ACK → Client ACK | **VERIFIED** |
| **03_TLS_Handshake** | Client → Edge (`10.7.28.232:8443`) | TLS 1.3 / Port 8443 | `ClientHello` with SNI `app.team1.test`, `ServerHello`, Certificate, Finished | **VERIFIED** |
| **04_TLS_Application_Data** | Client ↔ Edge (`10.7.28.232:8443`) | TLS Record 23 | Payload encrypted over Wi-Fi medium (`http-over-tls`) | **VERIFIED** |
| **05_Backend_A_Flow** | Edge (`10.7.28.232`) → Backend A (`10.7.9.142:3001`) | HTTP / TCP 3001 | Proxied GET request returning `X-Backend: Backend-A` | **VERIFIED** |
| **06_Backend_B_Flow** | Edge (`10.7.28.232`) → Backend B (`10.7.22.224:3002`) | HTTP / TCP 3002 | Proxied GET request returning `X-Backend: Backend-B` | **VERIFIED** |
| **07_Load_Balancing** | Client → Edge (`10.7.28.232:8443`) | HTTPS 8443 | Sequential requests alternating `X-Backend: Backend-A` and `Backend-B` | **VERIFIED** |
| **08_HTTP_Headers** | Backends → Edge → Client | HTTP Headers | `Cache-Control: max-age=60`, `Content-Type: application/json` | **VERIFIED** |

---

## 🔍 Wireshark Packet Inspection Log Summary

### 1. DNS Resolution
- **Client**: `10.7.28.232`
- **DNS Server**: `10.7.21.208:53`
- **Query**: `Standard query 0x... A app.team1.test`
- **Answer**: `app.team1.test: type A, class IN, addr 10.7.28.232`

### 2. Backend B Proxy Communication (Verified Wireshark Trace)
- `10.7.28.232` → `10.7.22.224:3002` `[SYN]`
- `10.7.22.224` → `10.7.28.232` `[SYN, ACK]`
- `10.7.28.232` → `10.7.22.224` `[ACK]`
- Request: `GET / HTTP/1.1` (Host: `app.team1.test`)
- Response: `HTTP/1.0 200 OK`
  ```http
  Server: BaseHTTP/0.6 Python/3.12.5
  Content-Type: application/json
  Content-Length: 93
  Cache-Control: max-age=60
  X-Backend: Backend-B
  ```
- JSON Payload:
  ```json
  {
      "message": "Hello from Backend B",
      "backend": "B",
      "server_ip": "10.7.22.224",
      "port": 3002
  }
  ```

---

## 📂 Evidence Storage Note
Raw `.pcapng` packet capture files (such as `Phase1_TLS_Handshake.pcapng`) and high-resolution Wireshark screenshots exported during testing are housed in this directory for live evaluation presentation.
