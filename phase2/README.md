# Phase 2 — Harden, Recover, Troubleshoot (Team 1)

Phase 2 extends the Phase 1 network. **Nothing is rebuilt.** Same LAN, same
names, same certificate, same backends (with additions). This folder is the
runbook: what to install, what to run on which Mac, and what you should see.

| Ext. | What | Where it lives |
| :-- | :-- | :-- |
| A | Backup DNS resolver on Mac 3 | `dns/phase2/`, `scripts/dns.sh`, `scripts/client-dns.sh` |
| B | TTL = 30 s, live record change, manual flush | `dns/phase2/team1.hosts`, `scripts/dns.sh point`, `scripts/ttl-watch.sh` |
| C | Backend ports reachable **only** from the edge (pf) + rollback | `scripts/firewall.sh`, `firewall/*.conf` |
| D | nginx detects a dead backend and fails over | `nginx/phase2/edge-primary.conf`, `nginx/phase2/proxy-common.conf` |
| E | Standby edge on Mac 4 + DNS-based cutover | `nginx/phase2/edge-standby.conf`, `scripts/dns.sh point standby` |
| F | Layer-by-layer diagnosis of an injected fault | `scripts/diagnose.py`, `docs/Troubleshooting-Playbook.md` |

All scripts read IPs from **`phase2/team.env`**. Run every command from the
repo root (`cd CN_HashNet`).

---

## 0. Phase 2 role map

```
                         ┌─────────────── private LAN 10.7.0.0/19 ───────────────┐
 Mac 1 10.7.21.208       Mac 2 10.7.28.232        Mac 3 10.7.9.142          Mac 4 10.7.22.224
 ─────────────────       ─────────────────        ────────────────          ─────────────────
 PRIMARY DNS :53         PRIMARY EDGE             Backend A :3001           Backend B :3002
 test client             nginx :8080/:8443        BACKUP DNS :53  (A)       STANDBY EDGE :8443 (E)
                         TLS + LB + failover (D)  pf isolation    (C)       pf isolation (C)
                                                                            test client
```

Request path (unchanged): client → DNS (Mac 1, or Mac 3 if Mac 1 is down) →
`app.team1.test` = Mac 2 (or Mac 4 after cutover) → nginx → Backend A / B.

**Three members, suggested split** (everyone must still be able to explain all of it):

| Member | Owns | Demo steps they drive |
| :-- | :-- | :-- |
| Member 1 — DNS | Mac 1 + backup DNS on Mac 3 | Ext A, Ext B, the DNS half of Ext E |
| Member 2 — Edge | Mac 2 + standby edge on Mac 4 | Ext D, the nginx half of Ext E |
| Member 3 — Backends & security | Mac 3/Mac 4 backends, pf rules, evidence | Ext C, captures, runs `diagnose.py` in Ext F |

> Only three laptops? Collapse roles like this and edit `phase2/team.env`,
> the `upstream` block in both `nginx/phase2/edge-*.conf` and
> `dns/phase2/team1.hosts` to match:
> L1 = primary DNS + Backend B + client, L2 = primary edge,
> L3 = Backend A + backup DNS + standby edge.

---

## 1. One-time setup

**All Macs**
```bash
git pull                      # get Phase 2 files
brew install dnsmasq nginx    # only where needed (see table above)
```

**Mac 3 and Mac 4 — new backend code** (adds `/health`, `/api/data` with ETag → 304, HEAD support)
```bash
python3 backend-a/server.py   # on Mac 3
python3 backend-b/server.py   # on Mac 4
```

**Mac 2 and Mac 4 — certificate for the edges**
```bash
cp /path/to/team1-server.crt /path/to/team1-server.key nginx/phase2/certs/
chmod 600 nginx/phase2/certs/team1-server.key
```
Transfer the key to Mac 4 with AirDrop/scp, never via GitHub (`certs/` is git-ignored).

**Any Mac running `diagnose.py`** — copy the *public* CA cert to `tls/team1-ca.crt`.

**Mac 2 — switch from the Phase 1 nginx to the Phase 2 config**
```bash
brew services stop nginx 2>/dev/null; sudo nginx -s stop 2>/dev/null   # free 8080/8443
./phase2/scripts/edge.sh start primary
```
`edge-*.conf` uses `http2 on;` (nginx ≥ 1.25.1; Homebrew ships newer). On an
older nginx, delete that line and write `listen 8443 ssl http2;` instead.

**Mac 1 and Mac 3 — Phase 2 dnsmasq** (stop the Phase 1 dnsmasq first)
```bash
./phase2/scripts/dns.sh start        # foreground, query log on screen
```

**Client Macs (Mac 1 and Mac 4)**
```bash
./phase2/scripts/client-dns.sh setup   # DNS = 10.7.21.208, then 10.7.9.142
./phase2/scripts/client-dns.sh show
```

**Baseline check** — everything should be PASS:
```bash
python3 phase2/scripts/diagnose.py
./phase2/scripts/probe.sh -n 6          # alternates Backend-A / Backend-B
```

---

## 2. Extension A — Backup DNS resolver

**Idea.** A resolver is a service like any other; one copy is a single point
of failure. The client gets two resolver addresses and moves on to the second
when the first doesn't answer.

| Step | Where | Command | Expected |
| :-- | :-- | :-- | :-- |
| 1 | Mac 4 | `dig @10.7.21.208 app.team1.test +short` and `dig @10.7.9.142 app.team1.test +short` | both: `10.7.28.232` |
| 2 | Mac 4 | start Wireshark, filter `dns` | |
| 3 | Mac 1 | `./phase2/scripts/dns.sh stop` | "dnsmasq stopped" |
| 4 | Mac 4 | `dig @10.7.21.208 app.team1.test` | `connection refused` (host up, port 53 closed) |
| 5 | Mac 4 | `./phase2/scripts/client-dns.sh flush` then `./phase2/scripts/probe.sh -n 4` | still 200 — the name resolved through Mac 3 |
| 6 | Mac 4 | `python3 phase2/scripts/diagnose.py` | primary DNS **WARN refused**, backup PASS, all layers OK |
| 7 | Mac 1 | `./phase2/scripts/dns.sh start` | restore |

**Evidence.** Wireshark: query → 10.7.21.208, *ICMP Destination unreachable (Port unreachable)*,
same query → 10.7.9.142, answer. Plus Mac 3's dnsmasq log showing the query.

**DNS failure vs. application failure.**
DNS down = `curl: (6) Could not resolve host`. Nothing reaches the edge, and
the name doesn't resolve even though every server is up.
Application down = name resolves, TCP + TLS to the edge work, and the edge
answers **502** (`edge reachable … but no backend answered`). Different
layer, different symptom, different fix.

---

## 3. Extension B — TTL and controlled record change

**Idea.** `local-ttl=30` makes dnsmasq send TTL 30. The client's resolver
(mDNSResponder) caches the answer for 30 s and does not ask again before then,
**even if the record changed**.

Use `curl`/`probe.sh` for this demo. Browsers keep their own DNS cache
(Chrome ≈ 60 s) on top of the OS one.

| Step | Where | Command |
| :-- | :-- | :-- |
| 1 | Mac 4 (window 1) | `./phase2/scripts/ttl-watch.sh` |
| 2 | Mac 4 (window 2) | `./phase2/scripts/probe.sh -i 2 -p /edge/health` (fills the cache) |
| 3 | Mac 1 **and** Mac 3 | `./phase2/scripts/dns.sh point standby` *(or any test IP, e.g. `dns.sh point 10.7.22.224`)* |
| 4 | watch | servers flip at once. `client-cache` keeps the **old** IP for up to 30 s, then flips |
| 5 | Mac 1 + Mac 3 | `./phase2/scripts/dns.sh point primary` |
| 6 | Mac 4 | immediately `./phase2/scripts/client-dns.sh flush` → `client-cache` flips with no wait |

`dig @server` always shows `TTL 30`, because dnsmasq serves local data with a
fixed TTL. The countdown happens in the **client's** cache, which is what
`ttl-watch.sh` shows in the first column.

**Production link.** Lower the TTL (e.g. 3600 → 60) a full old-TTL period
**before** a migration. Then change the record. Within one short TTL every
client follows. Keep the old server running until then, because cached
clients still use it.

---

## 4. Extension C — Service isolation (pf)

**Idea.** Clients should never talk to backends directly. pf on each backend
allows TCP to the backend port **only from the edge's IP** and silently drops
everyone else.

```bash
# Mac 3
./phase2/scripts/firewall.sh render A      # read the rules first (also in firewall/pf-backend-A.conf)
./phase2/scripts/firewall.sh apply A       # backs up pf state to firewall/backups/<time>/, loads, enables
# Mac 4
./phase2/scripts/firewall.sh apply B
```

| Test | From | Command | Expected |
| :-- | :-- | :-- | :-- |
| edge → backend | Mac 2 | `nc -vz -G 3 10.7.9.142 3001` / `curl http://10.7.9.142:3001/health` | succeeded / 200 |
| client → backend | Mac 1 | `nc -vz -G 3 10.7.9.142 3001` | **times out** (dropped, no RST) |
| client → backend | Mac 1 | `nc -vz -G 3 10.7.22.224 3002` | **times out** |
| client → service | Mac 1 | `./phase2/scripts/probe.sh -n 4` | 200, both backends — the path through the edge still works |
| counters | Mac 3 | `./phase2/scripts/firewall.sh status` | packet counts on the `block` rule went up |

Roll back after the demo (required):
```bash
./phase2/scripts/firewall.sh rollback      # reloads Apple's /etc/pf.conf, releases our pf enable token
```

`block drop` gives a timeout. `block return` would give an immediate
"connection refused". Drop is used here because it tells the scanner nothing.
Wireshark on Mac 1 shows SYN, SYN retransmissions and no SYN-ACK.

macOS's *Application Firewall* (System Settings → Network → Firewall) works
per app, not per source IP or port. That is why this uses pf.

---

## 5. Extension D — High-availability failover

**Config** (`proxy-common.conf` + `upstream` in `edge-primary.conf`):

* `max_fails=1 fail_timeout=10s` — one failed attempt takes the backend out
  of rotation for 10 s. After that nginx lets one real request through as a
  probe.
* `proxy_next_upstream error timeout http_502 http_503 http_504` with `tries 2`:
  the request that hit the dead backend is **re-sent to the other one**, so
  the client never sees the failure.
* `proxy_connect_timeout 2s` — a backend whose host vanished (no RST) is
  given up on after 2 s instead of the default 60 s.

| Step | Where | Command | Expected |
| :-- | :-- | :-- | :-- |
| 1 | Mac 2 | `./phase2/scripts/edge.sh logs primary` | |
| 2 | Mac 1 | `./phase2/scripts/probe.sh` | A, B, A, B … |
| 3 | Mac 3 | **Ctrl+C** Backend A | next request: `tried=[10.7.9.142:3001, 10.7.22.224:3002]` with **200**, then only Backend-B. **No failures** |
| 4 | Mac 2 log | | `connect() failed (61: Connection refused)` + `upstream server temporarily disabled` |
| 5 | Mac 3 | `python3 backend-a/server.py` | within ≤ 10 s, A reappears and the rotation resumes |
| 6 | Mac 1 | Ctrl+C on probe | summary: `HTTP-5xx=0 failed=0` |

What this looked like when tested here (loopback simulation, same configs):
A killed at 19:06:03 → one retried request, 23 requests served by B, zero errors.
A restarted at 19:06:11 → back in rotation at 19:06:15.

**Single point of failure.** The edge, Mac 2. If nginx or Mac 2 dies, DNS
still hands out 10.7.28.232 and every client fails at the TCP layer. To
remove it you need two or more edges plus a way to move traffic between them:

* **DNS-based** (Ext E): simple, but limited by TTL and needs someone (or a
  health checker) to change the record
* **Shared virtual IP** (VRRP/keepalived, or CARP on BSD): the standby takes
  over the IP in about a second, with no DNS change
* **Anycast or a managed load balancer** (AWS ALB/NLB spread across zones,
  Route 53 health-checked failover records)

The DNS servers have backups now. One SPOF is left in this design: **the
single Wi-Fi access point/router**.

---

## 6. Extension E — Controlled edge migration (DNS cutover)

```bash
# Mac 4 — bring up the standby edge (same config, same cert)
./phase2/scripts/edge.sh start standby
curl https://app.team1.test:8443/edge/health --resolve app.team1.test:8443:10.7.22.224   # X-Edge: standby-mac4
# If Ext C rules are loaded, let the standby reach Backend A as well:
#   Mac 3: ./phase2/scripts/firewall.sh apply A --with-standby
```

| Step | Where | Command | Expected |
| :-- | :-- | :-- | :-- |
| 1 | Mac 1 (client) | `./phase2/scripts/probe.sh -i 1` | `edge=10.7.28.232 (primary-mac2)` |
| 2 | Mac 4 (2nd client) | `./phase2/scripts/ttl-watch.sh` | |
| 3 | Mac 1 + Mac 3 | `./phase2/scripts/dns.sh point standby` (note the time) | |
| 4 | probe | still `primary-mac2` for up to 30 s (cached) → `==== edge address changed ====` → `standby-mac4` | |
| 5 | another client | `client-dns.sh flush` → standby immediately | old and new edge serving in parallel |
| 6 | Mac 2 | after the TTL, `edge.sh logs primary` goes quiet → safe to stop the primary | |
| 7 | rollback | `dns.sh point primary` on both DNS Macs | |

The certificate is valid on the standby because TLS checks the **name**
(`app.team1.test` is in the SAN), not the IP.

---

## 7. Extension F — Faculty fault

```bash
python3 phase2/scripts/diagnose.py                 # from a client
python3 phase2/scripts/diagnose.py --backends      # on Mac 2, if the verdict says HTTP/502
```
Then confirm by hand, one layer at a time, saying each step out loud.
`docs/Troubleshooting-Playbook.md` has the method, the manual commands, and
eight practice faults to run on each other before the evaluation.

---

## 8. Reset to normal after any demo

```bash
Mac 1, Mac 3:  ./phase2/scripts/dns.sh point primary
Mac 3, Mac 4:  ./phase2/scripts/firewall.sh rollback
Mac 4:         ./phase2/scripts/edge.sh stop standby
Clients:       ./phase2/scripts/client-dns.sh flush
Any:           python3 phase2/scripts/diagnose.py     # all PASS
```
