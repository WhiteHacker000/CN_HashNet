# Private Network Service Platform — Team 1
**Computer Networks Course Project | Phase 1 Submission**

---

## 1. Project Overview
The **Private Network Service Platform** is a two-phase, fully local networking project demonstrating real-world request lifecycle mechanics without cloud dependency. 

A client request resolves a private domain (`app.team1.test`) through a dedicated DNS server, establishes an encrypted HTTPS connection terminated at an Nginx edge reverse proxy, and is dynamically load balanced across two independent Python HTTP backend instances on a physical private local area network (LAN).

> **Core Principle**: *The application stays simple — the network is the project.*

---

## 2. Architecture
The architecture maps foundational networking concepts directly across four physical macOS nodes:
```
Client Machine 
    │
    ▼ [1] DNS Query (UDP Port 53)
Mac 1: Private DNS (dnsmasq @ 10.7.21.208)
    │   └── Resolves app.team1.test → 10.7.28.232
    │
    ▼ [2] HTTPS Request (TCP Port 8443 / TLS 1.3 Termination)
Mac 2: Edge Reverse Proxy & Load Balancer (Nginx @ 10.7.28.232)
    │
    ├───► [3a] Round-Robin Upstream Proxy ──► Mac 3: Backend A (Python @ 10.7.9.142:3001)
    └───► [3b] Round-Robin Upstream Proxy ──► Mac 4: Backend B (Python @ 10.7.22.224:3002)
```

---

## 3. Network Topology
- **Physical Medium**: Private Wi-Fi / Local Area Network Segment
- **Subnet**: `10.7.0.0/19` (`Netmask: 255.255.224.0`)
- **Default Gateway**: `10.7.0.1`
- **Private Domain Namespace**: `.test` (RFC 6761 reserved; prevents conflicts with macOS mDNS)

```
                              [ PRIVATE LAN (10.7.0.0/19) ]
                                             │
      ┌──────────────────────────────────────┼──────────────────────────────────────┐
      │                                      │                                      │
┌─────▼────────────────────────┐   ┌─────────▼────────────────────┐   ┌─────────────▼──────────────┐
│            MAC 1             │   │            MAC 2             │   │            MAC 3           │
│ • Role: Private DNS Server   │   │ • Role: Edge / Rev Proxy     │   │ • Role: Backend Instance A │
│ • IP: 10.7.21.208            │   │ • IP: 10.7.28.232            │   │ • IP: 10.7.9.142           │
│ • MAC: 10:9f:41:be:e0:72     │   │ • MAC: 10:9f:41:ba:34:c0     │   │ • Port: 3001 (Python REST) │
│ • Daemon: dnsmasq (Port 53)  │   │ • Server: Nginx (8080/8443)  │   │ • Header: X-Backend: A     │
│ • Domains: app.team1.test    │   │ • Function: TLS Termination, │   │ • Cache-Control: max-age=60│
│            api.team1.test    │   │   Round-Robin Load Balancer  │   └────────────────────────────┘
└──────────────────────────────┘   └─────────┬────────────────────┘
                                             │ (Proxy upstream traffic)
                                   ┌─────────▼────────────────────┐
                                   │            MAC 4             │
                                   │ • Role: Backend Instance B   │
                                   │ • IP: 10.7.22.224            │
                                   │ • MAC: 10:9f:41:b1:7a:fb     │
                                   │ • Server: Python (Port 3002) │
                                   │ • Header: X-Backend: B       │
                                   │ • Cache-Control: max-age=60  │
                                   └──────────────────────────────┘
```

---

## 4. Machine / IP / Service Table

| Machine | IP Address | Subnet / Gateway | Interface | MAC Address | Role | Service Daemon | Port(s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mac 1** | `10.7.21.208` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:be:e0:72` | Private DNS Server | `dnsmasq` | `53` (UDP/TCP) |
| **Mac 2** | `10.7.28.232` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:ba:34:c0` | Edge / Reverse Proxy | Nginx HTTP | `8080` (TCP) |
| **Mac 2** | `10.7.28.232` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:ba:34:c0` | Edge / TLS & LB | Nginx HTTPS | `8443` (TCP/TLS) |
| **Mac 3** | `10.7.9.142` | `255.255.224.0` / `10.7.0.1` | `en0` | *(Hardware mapped)* | Backend Server A | Python `http.server` | `3001` (TCP) |
| **Mac 4** | `10.7.22.224` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:b1:7a:fb` | Backend Server B | Python `http.server` | `3002` (TCP) |

---

## 5. Request Flow
1. **DNS Lookup**: Client requests `app.team1.test`. Query goes to Mac 1 (`10.7.21.208:53`), which answers with `10.7.28.232`.
2. **TCP 3-Way Handshake**: Client initiates TCP connection to Mac 2 on port `8443` (`SYN` → `SYN, ACK` → `ACK`).
3. **TLS Handshake**: Client and Mac 2 negotiate TLS 1.3 using certificates signed by the Team 1 Local Root CA.
4. **HTTPS Request**: Client sends encrypted `GET /api/status` over the established TLS tunnel.
5. **Reverse Proxy Dispatch**: Nginx decrypts request and proxies it to the `team1_backends` pool.
6. **Backend Processing**: Backend A (`10.7.9.142:3001`) or Backend B (`10.7.22.224:3002`) receives the request, generates JSON, and sets `X-Backend` and `Cache-Control: max-age=60`.
7. **Response Delivery**: Nginx receives backend response, encrypts it via TLS, and returns `200 OK` to the client.

---

## 6. Private DNS
- Hosted on **Mac 1** (`10.7.21.208`) using `dnsmasq`.
- Records:
  - `app.team1.test → 10.7.28.232`
  - `api.team1.test → 10.7.28.232`
- Configured in [dns/team1.conf](file:///Users/whitedarkhost/Documents/CN_HashNet/dns/team1.conf).
- Verified with `dig @10.7.21.208 app.team1.test`.

---

## 7. Backend A
- Runs on **Mac 3** (`10.7.9.142:3001`) implemented in Python (`http.server`).
- Binds to `0.0.0.0:3001` for LAN accessibility.
- Returns header: `X-Backend: Backend-A` and `Cache-Control: max-age=60`.
- Verified response:
  ```json
  {
      "status": "ok",
      "backend": "A",
      "server_ip": "10.7.9.142",
      "port": 3001
  }
  ```

---

## 8. Backend B
- Runs on **Mac 4** (`10.7.22.224:3002`) implemented in Python (`http.server`).
- Binds to `0.0.0.0:3002` for LAN accessibility.
- Returns header: `X-Backend: Backend-B` and `Cache-Control: max-age=60`.
- Verified response:
  ```json
  {
      "status": "ok",
      "backend": "B",
      "server_ip": "10.7.22.224",
      "port": 3002
  }
  ```

---

## 9. Nginx Reverse Proxy
- Runs on **Mac 2** (`10.7.28.232`).
- Acts as the single entry point so clients never communicate directly with backend IPs.
- Forwards client headers (`Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`).
- Configured in [nginx/team1.conf](file:///Users/whitedarkhost/Documents/CN_HashNet/nginx/team1.conf).

---

## 10. Load Balancing
- Upstream group `team1_backends` load balances requests between Mac 3 and Mac 4 via round-robin.
- Sequential requests alternate responses between `X-Backend: Backend-A` and `X-Backend: Backend-B`.

---

## 11. HTTPS / TLS
- Local Root Certificate Authority generated with OpenSSL.
- Edge certificate contains Subject Alternative Names (SAN): `DNS.1 = app.team1.test`, `DNS.2 = api.team1.test`.
- Root CA imported into client macOS System Keychain.
- **Verified without insecure flag**: `curl https://app.team1.test:8443/api/status` succeeds cleanly without `-k`.
- Private keys (`*.key`, `*.pem`) are strictly excluded from version control for security.

---

## 12. HTTP Caching
- **Verified**: Backend responses return `Cache-Control: max-age=60`.
- **Pending Verification**: Demonstration of conditional HTTP requests returning `304 Not Modified` or browser cache-hit validation is marked as **PENDING VERIFICATION**.

---

## 13. Wireshark Evidence
Comprehensive packet traces captured across the network demonstrate:
1. **DNS Resolution**: Standard query `A app.team1.test` to `10.7.21.208:53` returning `10.7.28.232`.
2. **TCP 3-Way Handshake**: `SYN` → `SYN, ACK` → `ACK` on port 8443.
3. **TLS Handshake**: `ClientHello` (with SNI), `ServerHello`, Certificate delivery, and Key Exchange.
4. **Encrypted Payload**: Application data transported as `http-over-tls` (TLS Record Type 23).
5. **Upstream Proxy**: Plain HTTP exchanges on ports 3001 and 3002 between Mac 2 and Mac 3 / Mac 4.

---

## 14. Verification Commands

```bash
# 1. Test DNS Resolution
dig @10.7.21.208 app.team1.test

# 2. Test Edge HTTP Entry Point
curl -i http://app.team1.test:8080/api/status

# 3. Test Edge HTTPS Entry Point (Valid CA, no -k)
curl -i https://app.team1.test:8443/api/status

# 4. Verify Load Balancing Alternation
for i in {1..4}; do curl -sI https://app.team1.test:8443/api/status | grep X-Backend; done
```

---

## 15. Failure Demonstration D3
- **Scenario D3**: One backend stopped (e.g., stopping Backend A on Mac 3).
- **Expected Behavior**: Nginx detects upstream unavailability and continues serving all client requests through the remaining healthy backend (Backend B on Mac 4).
- **Current Status**: **Phase 1 D3 failover behavior is pending final verification.**

---

## 16. Troubleshooting Methodology
When isolating issues across the stack, diagnose layer-by-layer:
1. **Name Resolution (Application / DNS)**: Run `dig app.team1.test` to verify IP resolution before testing HTTP.
2. **IP Reachability (Network / IP)**: Run `ping <IP>` to test physical LAN routing.
3. **Port Connectivity (Transport / TCP)**: Run `nc -zv <IP> <Port>` to test socket connectivity before application debugging.
4. **TLS Layer (Session / Security)**: Run `openssl s_client -connect app.team1.test:8443 -servername app.team1.test` to inspect certificate chains.
5. **Application Layer (HTTP / REST)**: Run `curl -v` to inspect HTTP response codes and headers.

---

## 17. Tools Used
- **Operating System**: macOS (Apple Silicon / Intel)
- **DNS Server**: `dnsmasq`
- **Reverse Proxy / Load Balancer**: `nginx`
- **Backend Runtimes**: Python 3 standard library (`http.server`, `json`)
- **Diagnostic / Observability Tools**: `Wireshark`, `curl`, `dig`, `nslookup`, `ping`, `pfctl`
- **Cryptography**: `OpenSSL`

---

## 18. Project Constraints & Compliance
- ✅ **Fully Local**: Zero cloud hosting; all services run on laptops connected to a physical LAN.
- ✅ **Standard Namespace**: Uses reserved `.test` TLD (RFC 6761) to avoid macOS Bonjour/mDNS issues.
- ✅ **Security**: Private keys are excluded from git; HTTPS validates cleanly against local CA.
- ✅ **Unprivileged Ports**: Edge uses `8080`/`8443` and backends use `3001`/`3002`.

---

## 19. Team Members & Responsibility Matrix
The team consists of 5 members managing 4 infrastructure laptops:
- **Mac 1 (Member 1)**: Private DNS Resolver (`dnsmasq`) & Test Client
- **Mac 2 (Member 2)**: Edge Reverse Proxy, TLS Termination & Load Balancer (`nginx`)
- **Mac 3 (Member 3)**: Backend Instance A (`Python http.server:3001`)
- **Mac 4 (Member 4)**: Backend Instance B (`Python http.server:3002`) & Test Client
- **Member 5**: Wireshark Packet Capture, Evidence Documentation & Live Presentation

---

## 20. Phase 1 Status
**Phase 1 Gate Criteria**:
- [x] Client resolves `app.team1.test` via team DNS server (`10.7.21.208`)
- [x] Client connects over HTTPS (`https://app.team1.test:8443`) without `-k`
- [x] Load balancer serves responses alternately from Backend A and Backend B
- [x] Wireshark captures prove DNS, TCP 3-way handshake, TLS handshake, and HTTP headers
- [ ] Phase 1 D3 failover behavior is pending final verification
- [ ] Explicit 304 Not Modified / browser cache-hit demonstration is pending verification
