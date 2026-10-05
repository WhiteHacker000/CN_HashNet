# Machine / IP / Service Inventory Table

| Machine | IP Address | Subnet Mask / Gateway | Interface | MAC Address | Role | Service | Port(s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mac 1** | `10.7.21.208` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:be:e0:72` | Private DNS | `dnsmasq` | `53` (UDP/TCP) |
| **Mac 2** | `10.7.28.232` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:ba:34:c0` | Edge / Rev Proxy | Nginx HTTP | `8080` (TCP) |
| **Mac 2** | `10.7.28.232` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:ba:34:c0` | Edge / TLS & LB | Nginx HTTPS | `8443` (TCP/TLS) |
| **Mac 3** | `10.7.9.142` | `255.255.224.0` / `10.7.0.1` | `en0` | *(Hardware mapped)* | Backend A | Python REST | `3001` (TCP) |
| **Mac 4** | `10.7.22.224` | `255.255.224.0` / `10.7.0.1` | `en0` | `10:9f:41:b1:7a:fb` | Backend B | Python REST | `3002` (TCP) |

---

### Network Parameters
- **Subnet**: `10.7.0.0/19` (`Netmask: 255.255.224.0`)
- **Default Gateway**: `10.7.0.1`
- **DNS Server**: `10.7.21.208`
- **Private Domain Namespace**: `.test` (RFC 6761 reserved)
