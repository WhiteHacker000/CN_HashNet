# Private DNS Subsystem (Mac 1)

## 📌 Overview
The Private DNS Server is hosted on **Mac 1** (`10.7.21.208`) using `dnsmasq`. It acts as the authoritative local name server for the reserved `.test` private domain namespace (RFC 6761).

The `.test` top-level domain is specifically chosen to prevent naming conflicts with macOS Bonjour / mDNS (`.local`).

---

## ⚙️ DNS Record Mappings

| Domain Name | Record Type | Target IP Address | Represents |
| :--- | :--- | :--- | :--- |
| `app.team1.test` | `A` | `10.7.28.232` | Mac 2 (Edge Nginx Reverse Proxy / Load Balancer) |
| `api.team1.test` | `A` | `10.7.28.232` | Mac 2 (Secondary API domain) |

---

## 🚀 How to Run `dnsmasq` on Mac 1

1. **Install dnsmasq** (via Homebrew):
   ```bash
   brew install dnsmasq
   ```

2. **Launch dnsmasq in foreground with debug query logging**:
   ```bash
   sudo dnsmasq --no-daemon --conf-file=$(pwd)/dns/team1.conf
   ```

---

## 💻 Client Machine Configuration

On all client Macs (Mac 2, Mac 3, Mac 4, and testing clients):
1. Open **System Settings / Preferences** → **Network** → **Wi-Fi / Ethernet** → **Details** → **DNS**.
2. Add `10.7.21.208` as the primary DNS server.
3. Apply changes and flush local DNS cache:
   ```bash
   sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
   ```

---

## 🔍 Verification & Evidence Commands

Verify that the local DNS server is resolving the domain correctly:

```bash
# Query specifically against Mac 1
dig @10.7.21.208 app.team1.test

# Expected Output excerpt:
# ;; ANSWER SECTION:
# app.team1.test.        0       IN      A       10.7.28.232
# ;; SERVER: 10.7.21.208#53(10.7.21.208)

# Alternative nslookup verification
nslookup app.team1.test 10.7.21.208
```
