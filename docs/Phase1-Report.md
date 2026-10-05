# Computer Networks Course Project — Phase 1 Report
**Project Title**: Private Network Service Platform  
**Team**: Team 1  
**Target Environment**: 4 macOS Laptops (Local LAN / No Cloud)  

---

## 1. Objective
The objective of Phase 1 is to build, observe, and document a fully local private service environment across physical laptops on a shared LAN segment. The project demonstrates real-world protocol mechanics across the network stack: Private DNS resolution, TCP three-way handshake, TLS 1.2/1.3 termination, Nginx reverse proxy load balancing, HTTP REST backend services, HTTP caching headers, and comprehensive packet analysis using Wireshark.

---

## 2. Architecture
The architecture comprises a client machine, an authoritative local DNS resolver, an edge reverse proxy load balancer, and two decoupled backend instances. All nodes communicate over a private IPv4 local network (`10.7.0.0/19`) using the reserved `.test` domain namespace.

```
Client Machine 
    │
    ▼ (1) DNS Query (UDP 53)
Mac 1: dnsmasq (10.7.21.208)  ───> Resolves app.team1.test to 10.7.28.232
    │
    ▼ (2) HTTPS Request (Port 8443 / TLS Termination)
Mac 2: Nginx Edge & Load Balancer (10.7.28.232)
    │
    ├───> (3a) Round-Robin ───> Mac 3: Backend A (10.7.9.142:3001) [X-Backend: Backend-A]
    └───> (3b) Round-Robin ───> Mac 4: Backend B (10.7.22.224:3002) [X-Backend: Backend-B]
```

---

## 3. Machine Roles & IP Inventory

| Machine | IP Address | Subnet / Gateway | Primary Role | Software / Service | Ports |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Mac 1** | `10.7.21.208` | `255.255.224.0` / `10.7.0.1` | Private DNS Resolver | `dnsmasq` | `53` (UDP/TCP) |
| **Mac 2** | `10.7.28.232` | `255.255.224.0` / `10.7.0.1` | Edge Proxy & Load Balancer | Nginx (HTTP/HTTPS) | `8080`, `8443` |
| **Mac 3** | `10.7.9.142` | `255.255.224.0` / `10.7.0.1` | Backend Instance A | Python `http.server` | `3001` |
| **Mac 4** | `10.7.22.224` | `255.255.224.0` / `10.7.0.1` | Backend Instance B | Python `http.server` | `3002` |

*Note: Team Member 5 is responsible for packet capture, evidence curation, and documentation.*

---

## 4. DNS Configuration
Mac 1 runs `dnsmasq` listening on `0.0.0.0:53`. It authoritatively maps:
- `app.team1.test` → `10.7.28.232`
- `api.team1.test` → `10.7.28.232`

Clients configure `10.7.21.208` as their primary DNS server. Queries for external domains are forwarded to public upstream resolvers (`8.8.8.8`, `1.1.1.1`).

---

## 5. Backend Services
Both backends are implemented using Python's standard `http.server` module with zero third-party dependencies:
- **Backend A** (`10.7.9.142:3001`): Returns `X-Backend: Backend-A` and JSON payload.
- **Backend B** (`10.7.22.224:3002`): Returns `X-Backend: Backend-B` and JSON payload.
- **Endpoints**: `GET /` and `GET /api/status`. Both services attach `Cache-Control: max-age=60` and bind to `0.0.0.0` for LAN reachability.

---

## 6. Nginx Configuration
Mac 2 runs Nginx acting as a reverse proxy with an upstream pool:
```nginx
upstream team1_backends {
    server 10.7.9.142:3001;
    server 10.7.22.224:3002;
}
```
Nginx handles client connections on port `8080` (HTTP) and port `8443` (HTTPS with TLS), sets proxy headers (`Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`), and forwards backend response headers to clients.

---

## 7. TLS Configuration
A custom two-tier PKI was created using OpenSSL:
1. **Team 1 Root CA**: Self-signed local Certificate Authority (`team1-ca.crt`).
2. **Edge Server Certificate**: Signed by Team 1 Root CA with Subject Alternative Names: `DNS.1 = app.team1.test`, `DNS.2 = api.team1.test`.

The Root CA was imported into the macOS System Keychain on client laptops, enabling native TLS validation in browsers and `curl` without using `-k`. Private keys are strictly protected and excluded from version control.

---

## 8. Load Balancing
Nginx distributes incoming requests to `https://app.team1.test:8443` across Backend A and Backend B using round-robin scheduling. Repeated curl requests demonstrate alternate `X-Backend` response headers between `Backend-A` and `Backend-B`.

---

## 9. HTTP Caching
- **Status**: **VERIFIED** for `Cache-Control: max-age=60` header generation from backend services and passthrough by Nginx.
- **Pending Verification**: Explicit `304 Not Modified` conditional request demonstration and browser-level cache-hit timing are marked as **PENDING VERIFICATION**.

---

## 10. Wireshark Evidence
Packet traces collected on the network verify:
1. **DNS Query & Answer**: `app.team1.test` resolving to `10.7.28.232` over UDP port 53.
2. **TCP 3-Way Handshake**: `SYN` → `SYN, ACK` → `ACK` on port 8443.
3. **TLS Handshake**: `ClientHello` (with SNI), `ServerHello`, Certificate delivery, and Cipher negotiation.
4. **Application Data**: Encrypted record exchange (`http-over-tls`).
5. **Backend Upstream Flow**: Plain HTTP proxying between Mac 2 and Mac 3/4 on ports 3001/3002.

---

## 11. Verification Results

| Verification Item | Test Performed | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **LAN Ping** | `ping 10.7.28.232` | 0% packet loss | Bidirectional connectivity across all 4 Macs | **VERIFIED** |
| **DNS Resolution** | `dig @10.7.21.208 app.team1.test` | Resolves to `10.7.28.232` | Returned `10.7.28.232` from server `10.7.21.208#53` | **VERIFIED** |
| **Backend A Direct** | `curl -i http://10.7.9.142:3001/api/status` | JSON + `X-Backend: Backend-A` | `200 OK`, `X-Backend: Backend-A` | **VERIFIED** |
| **Backend B Direct** | `curl -i http://10.7.22.224:3002/api/status` | JSON + `X-Backend: Backend-B` | `200 OK`, `X-Backend: Backend-B` | **VERIFIED** |
| **Nginx HTTPS** | `curl -i https://app.team1.test:8443/api/status` | 200 OK without `-k` | Verified with valid trusted certificate | **VERIFIED** |
| **Load Balancing** | Sequential HTTPS requests | Alternating backends | Alternated `Backend-A` and `Backend-B` | **VERIFIED** |
| **Cache-Control** | Inspect HTTP headers | `max-age=60` | Header present in response | **VERIFIED** |
| **304 Not Modified** | Conditional caching request | 304 response | Demonstration scheduled | **PENDING VERIFICATION** |

---

## 12. Failure Demonstration D3 (One Backend Stopped)
- **Scenario**: When one backend instance (e.g., Backend A on Mac 3) is stopped, the edge proxy should route all subsequent requests to the remaining healthy backend (Backend B on Mac 4).
- **Current Status**: **PENDING FINAL VERIFICATION**. Failover parameters (`proxy_next_upstream`) are documented and scheduled for live demonstration during evaluation.

---

## 13. Challenges & Troubleshooting Methodology
1. **macOS mDNS Conflict**: Solved by using the `.test` reserved TLD instead of `.local`, which macOS reserves for Bonjour multicast DNS.
2. **Interface Binding**: Ensured backends bind to `0.0.0.0` rather than `127.0.0.1` so that requests across the physical LAN are accepted.
3. **Port Permissions**: Utilized unprivileged ports `8080` (HTTP) and `8443` (HTTPS) to ensure smooth execution without requiring non-standard root privileges on edge nodes.

---

## 14. Conclusion
Phase 1 core infrastructure is functional and satisfies all mandatory build tasks: LAN connectivity, authoritative DNS resolution, TLS termination, Nginx reverse proxy load balancing, Python HTTP backends, and Wireshark protocol verification. Phase 1 gate criteria have been successfully achieved.
