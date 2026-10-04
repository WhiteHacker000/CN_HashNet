# Network Inventory & Host Configuration (Task A)

## 📋 Team Machine Inventory

As required by **Phase 1 Task A**, here is the recorded network configuration for all machines on the private LAN.

| Machine | Assigned Role | IPv4 Address | Subnet Mask / CIDR | Default Gateway | Active Interface | MAC Address (Hardware Address) | Services / Ports |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mac 1** | **Primary DNS Server + Test Client** | `10.7.21.208` | `255.255.224.0` (`/19`) | `10.7.0.1` | `en0` | `10:9f:41:be:e0:72` | `dnsmasq` (Port 53 UDP/TCP) |
| **Mac 2** | **Edge Reverse Proxy & Load Balancer** | *(Pending)* | *(Pending)* | *(Pending)* | `en0` | *(Pending)* | `nginx` (Port 443 / 8443) |
| **Mac 3** | **Backend Server A** | *(Pending)* | *(Pending)* | *(Pending)* | `en0` | *(Pending)* | Node.js (Port 3001) |
| **Mac 4** | **Backend Server B + Backup DNS** | *(Pending)* | *(Pending)* | *(Pending)* | `en0` | *(Pending)* | Node.js (Port 3002), `dnsmasq` |

---

## 🔍 Mac 1 (DNS Server) Detailed Specifications

```yaml
Role: Primary DNS Server & Client
IPv4 Address: 10.7.21.208
Subnet Mask: 255.255.224.0 (/19)
Network Gateway: 10.7.0.1
Network Interface: en0
MAC Address: 10:9f:41:be:e0:72
DNS Daemon: dnsmasq
Listening Port: 53 (UDP/TCP)
Configured Domains:
  - app.team1.test -> <Mac 2 IP>
  - api.team1.test -> <Mac 2 IP>
```

---

## 🛠️ Verification Commands

To verify connectivity and configuration from any machine on the network:

1. **Ping Mac 1 (Reachability Test)**:
   ```bash
   ping -c 4 10.7.21.208
   ```

2. **Test DNS Resolution directly against Mac 1**:
   ```bash
   dig @10.7.21.208 app.team1.test
   nslookup app.team1.test 10.7.21.208
   ```

3. **Check ARP Table (Verifies MAC address mapping)**:
   ```bash
   arp -a | grep 10.7.21.208
   # Expected output: (10.7.21.208) at 10:9f:41:be:e0:72 on en0 ifscope [ethernet]
   ```
