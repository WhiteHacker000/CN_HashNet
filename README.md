# CN_HashNet — Private Network Service Platform
**Computer Networks Course Project | Team of 4 Members**

A two-phase, fully local networking project demonstrating DNS resolution, TLS termination, Reverse Proxy Load Balancing, HTTP/REST services, Caching, Protocol Packet Analysis, and High-Availability Failover across 4 macOS laptops on a shared LAN.

---

## 👥 Team Roles & Responsibilities (4 Mac Topology)

```
                       [ Private Wi-Fi / LAN Router ]
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       │                              │                              │
 ┌─────▼───────────────┐     ┌────────▼────────────┐     ┌───────────▼───────────┐
 │       MAC 1         │     │        MAC 2        │     │         MAC 3         │
 │ • Primary DNS       │     │ • Edge / Rev Proxy  │     │ • Backend Server A    │
 │   (dnsmasq:53)      │     │ • Load Balancer     │     │   (Node.js port 3001) │
 │ • Test Client       │     │ • TLS Termination   │     │ • Wireshark Capture   │
 │ • dig, curl, Wireshark    │   (nginx:443/8443)  │     │                       │
 └─────────────────────┘     └─────────┬───────────┘     └───────────────────────┘
                                       │ (upstream proxy)
                             ┌─────────▼───────────┐
                             │        MAC 4        │
                             │ • Backend Server B  │
                             │   (Node.js port 3002│
                             │ • Backup DNS (Ph. 2)│
                             │ • Test Client       │
                             └─────────────────────┘
```

| Machine | Role | Primary Services | Course Equivalents | Assigned Member |
| :--- | :--- | :--- | :--- | :--- |
| **Mac 1** | **Primary DNS + Test Client** | `dnsmasq` (Port 53), `dig`, `curl`, browser | AWS Route 53 / Local DNS Resolver | **Member 1** |
| **Mac 2** | **Edge / Reverse Proxy & Load Balancer** | `nginx` (Port 443 / 8443), SSL/TLS Certs | AWS ALB / Cloudflare / Cloud Edge | **Member 2** |
| **Mac 3** | **Backend Instance A** | Backend REST App (Port 3001), PF Firewall | Application Server A / EC2 Instance | **Member 3** |
| **Mac 4** | **Backend Instance B + Backup DNS** | Backend REST App (Port 3002), Backup `dnsmasq`, Test Client | Application Server B + Secondary DNS | **Member 4** |

---

## 📋 Network IP Table (Fill this before testing)

Connect all 4 Macs to the **same Wi-Fi or mobile hotspot**. Find each IP using `ipconfig getifaddr en0` or `ifconfig | grep inet`.

| Machine | Hostname / Role | Private IPv4 Address | Subnet / Gateway | Interface | MAC Address | Exposed Ports |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mac 1** | `dns-primary.team1.test` | `10.7.21.208` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:be:e0:72` | UDP/TCP 53 |
| **Mac 2** | `app.team1.test` / `api.team1.test` | `Pending` | `255.255.224.0` / `10.7.0.1` | `en0` | `Pending` | TCP 443 (8443) |
| **Mac 3** | `backend-a.team1.test` | `Pending` | `255.255.224.0` / `10.7.0.1` | `en0` | `Pending` | TCP 3001 |
| **Mac 4** | `backend-b.team1.test` | `Pending` | `255.255.224.0` / `10.7.0.1` | `en0` | `Pending` | TCP 3002, UDP 53 |

---

## 🚀 Quick Setup Instructions

### 1. Prerequisites (All Macs)
Install Homebrew and required CLI tools:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install node curl bind # provides dig, nslookup
```

### 2. Mac 1 Setup (Primary DNS)
```bash
cd dns
# 1. Update dnsmasq.conf with Mac 2's IP address
# 2. Start dnsmasq
sudo ./start_dns.sh
```

### 3. Mac 2 Setup (Edge Nginx + TLS)
```bash
cd nginx
# 1. Generate local SSL Certificate Authority & domain certs
./generate_certs.sh
# 2. Update nginx.conf with Mac 3 & Mac 4 IPs
# 3. Start Nginx
sudo nginx -c $(pwd)/nginx.conf
```
*Distribute `certs/ca.crt` to all Macs and trust it (`sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain certs/ca.crt`).*

### 4. Mac 3 & Mac 4 Setup (Backends)
```bash
cd backend
npm install
# On Mac 3:
PORT=3001 BACKEND_ID=A node server.js
# On Mac 4:
PORT=3002 BACKEND_ID=B node server.js
```

---

## 🧪 Phase 1 & 2 Verification Checklist

- [ ] **Task A (LAN)**: All 4 Macs can ping each other's IP addresses.
- [ ] **Task B (DNS)**: `dig @<Mac1-IP> app.team1.test` returns Mac 2's IP. Client system DNS set to Mac 1.
- [ ] **Task C (Backends)**: `http://<Mac3-IP>:3001/api/status` & `http://<Mac4-IP>:3002/api/status` return JSON.
- [ ] **Task D (Load Balancer)**: Repeated `curl -k https://app.team1.test/api/status` alternates headers `X-Backend: A` and `X-Backend: B`.
- [ ] **Task E (HTTPS/TLS)**: `curl https://app.team1.test/api/status` works without `-k` (valid CA trust).
- [ ] **Task F (Caching)**: `curl -I https://app.team1.test/api/cached-data` shows `Cache-Control` and returns `304 Not Modified` on `If-None-Match`.
- [ ] **Task G (Wireshark)**: Captured DNS Query/Response, TCP 3-Way Handshake (SYN, SYN-ACK, ACK), TLS Handshake (ClientHello, ServerHello, Certificate), and encrypted Application Data.
- [ ] **Phase 2 (Resilience & Failover)**:
  - Stop Backend A -> Nginx automatically routes all requests to Backend B without downtime.
  - Backup DNS on Mac 4 takes over when Mac 1 `dnsmasq` is stopped.
  - PF firewall on Mac 3 blocks direct access from client Macs while allowing Mac 2 (Edge).