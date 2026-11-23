# Phase 2 Final Report — Team 1: Harden, Recover, Troubleshoot

> Results below are from the live run on 2026-11-24. Remaining `⟨…⟩` fields
> (faculty fault, optional flush screenshot) are filled in after the evaluation.

## 1. What changed from Phase 1

| Area | Phase 1 | Phase 2 |
| :-- | :-- | :-- |
| DNS | one dnsmasq on Mac 1, records as `address=` lines, TTL 0 | identical dnsmasq on Mac 1 (primary) **and Mac 3 (backup)**; records in `dns/phase2/team1.hosts`, TTL 30 s, changed live with SIGHUP; `no-resolv`, `local=/team1.test/` |
| Clients | one resolver (Mac 1) | two resolvers: Mac 1, then Mac 3 |
| Edge | nginx round-robin, no failure handling | passive health checks (`max_fails=1 fail_timeout=10s`), retry on the other backend (`proxy_next_upstream`), 2 s connect timeout, JSON 502 page, `/edge/health`, `X-Edge` and debug upstream headers, upstream logged per request |
| Edge redundancy | none | identical standby nginx on Mac 4 (`edge-standby.conf`), same certificate |
| Backends | `/`, `/api/status` | + `/health`, `/api/data` (ETag shared by both backends → `304 Not Modified`), HEAD support, threaded server |
| Security | backends reachable from anywhere on the LAN | pf on Mac 3/Mac 4: backend port accepts only the edge; scripted backup + rollback |
| Operations | manual commands | `phase2/scripts/*` + `diagnose.py` layer-by-layer checker |

Phase 1 items that were pending are closed by Phase 2: the **304** demo
(`/api/data`) and **one backend stopped** (Extension D).

## 2. Resilience tests and results

All tests run live on 2026-11-24 (01:30–02:33 IST) on the four team Macs:

| Mac | Laptop | IP | Phase 2 role |
| :-- | :-- | :-- | :-- |
| Mac 1 | Kushal | 10.7.11.54 | primary DNS + test client |
| Mac 2 | Vansh | 10.7.24.242 | primary edge (nginx) |
| Mac 3 | Tejas | 10.7.11.60 | Backend A + backup DNS |
| Mac 4 | Anant | 10.7.8.22 | Backend B + standby edge |

**Baseline (01:41).** `diagnose.py` from Kushal's Mac passed every layer: both
resolvers answered `10.7.24.242` with TTL 30 s, ping 0 % loss, TCP handshake
13 ms, TLS 1.3 (`TLS_AES_256_GCM_SHA384`) with a cert for
`app.team1.test,api.team1.test` from *Team1 Local CA*, and load balancing
across Backend-A and Backend-B. A 22-request probe split exactly 11 / 11.

| # | Test | Expected | Observed (real run) |
| :-- | :-- | :-- | :-- |
| **A1** | Stop dnsmasq on Mac 1, resolve from Mac 4 | name still resolves via backup | `diagnose`: primary **REFUSED**, backup PASS, system resolver `app.team1.test -> 10.7.24.242`; probe 4/4 **200** |
| **A2** | Client cost of primary DNS failure | small delay, no error | 1st request **2.18–2.29 s** (resolver timeout on Mac 1, retry on Mac 3), next requests 0.06–0.14 s |
| **A3** | Backup DNS really served the client | queries visible on Mac 3 | `tcpdump` on Mac 3 shows Mac 4's queries (`10.7.8.22 → 10.7.11.60.53`) and answers |
| **A4** | DNS failure vs. application failure | different layers | with both backends down, DNS/IP/TCP/TLS/edge all PASS, `/api/status` → **502**: application failure, not DNS |
| **B1** | TTL in answers | 30 | `app.team1.test. 30 IN A 10.7.24.242` from both servers |
| **B2** | Record changed (Mac 3 02:21:26, Mac 1 02:21:41) | client keeps old IP ≤ TTL | client cache stayed `10.7.24.242` until 02:21:53, switched at **02:21:56** (15 s after the last server change) |
| **B2b** | Record changed back (both 02:22:32) | ≤ TTL | client switched at **02:23:13** (41 s: TTL 30 s refreshed just before the change + macOS cache refresh) |
| **B3** | Manual flush (`dscacheutil -flushcache` + HUP mDNSResponder) | immediate | flush command demonstrated; *timing screenshot: ⟨fill if B3 rerun is done⟩* |
| **C1** | Edge (Mac 2) → 3001 / 3002 with pf | connects | `nc` **succeeded** to both |
| **C2** | Client (Mac 1) → 3001 / 3002 with pf | dropped | `nc: … Operation timed out` on both |
| **C3** | Service via edge with pf | 200, both backends | 4/4 **200**, A 2 / B 2 |
| **C4** | pf counters (Mac 3) | pass carries edge traffic, block catches client | `pass … <team1_edges> port 3001`: **307 packets, 24 states**; `block drop … port 3001`: **3 packets** (Mac 1's SYN + 2 retransmissions) |
| **C5** | Rollback | direct access restored, pf back to prior state | `nc` succeeded again; Mac 4: `pf disabled` (was disabled before); Mac 3: "1 more pf enable reference, pf still enabled" (was already enabled before), so each Mac returned to its own original state; `diagnose` all PASS |
| **D1** | Backend A stopped during continuous probe (~01:46:20) | 0 errors, retry on B | **71 requests, 0 failed, 0 × 5xx.** First request after the stop: `tried=[10.7.11.60:3001, 10.7.8.22:3002]` → 200 |
| **D2** | Passive health check while A is down | periodic probe of A | A re-tried every ~14–15 s (#7, #18, #30, #41), each time `connect() failed (61: Connection refused)` + `upstream server temporarily disabled`, request transparently served by B |
| **D3** | Backend A restarted | back in rotation ≤ 10 s | A back at the first request after restart (**#53, 01:47:19**), strict A/B alternation resumed |
| **D4** | Both backends stopped | JSON 502, edge alive | `HTTP/2 502` `{"error":"bad_gateway",…"edge reachable (DNS, TCP and TLS OK) but no backend answered"}`; `/edge/health` → **200** |
| **E1** | Standby edge on Mac 4 | valid TLS without `-k` | `{"edge":"standby","host":"mac4","status":"ok"}` with the same certificate |
| **E2** | DNS cutover to standby | cached clients stay on Mac 2, then move | `served-by=primary-mac2` until 02:21:53, `served-by=standby-mac4` from **02:21:56**, back to primary at 02:23:13; **no failed request** during either move |
| **E3** | Combined failure (bonus) | still served | with primary DNS down **and** Backend A down at the same time: 4/4 **200** (02:07:40) |

## 3. Troubleshooting findings

Real faults we hit while deploying Phase 2, and how we isolated them layer by layer:

| Fault | Symptom seen | Layer identified | How we proved it | Fix |
| :-- | :-- | :-- | :-- | :-- |
| Old pf anchor `team1` on Mac 3 (left over from another project) allowed only `10.7.1.19` to ports 3001/3002 | Edge → Backend A **timed out**; Backend A answered locally on Mac 3 | Transport (packet filter on the backend host) | Timeout (not refused) = SYN dropped; app firewall already allowed python; `pfctl -sA` showed anchor `team1` with `block drop … port 3001`; `curl` worked the moment pf was disabled (`pfctl -d`) | `sudo pfctl -a team1 -F rules` (also needed after every `pfctl -f /etc/pf.conf`, since `/etc/pf.conf` loads that anchor at boot) |
| Homebrew's dnsmasq service on Mac 1 (Phase 1 config) running next to ours | Mac 1 answered `10.7.28.232` with **TTL 0** (old record) while Mac 3 answered `10.7.24.242` TTL 30 | DNS (wrong server process answering) | `lsof -iUDP:53`: two dnsmasq processes; the old one bound `10.7.11.54:53` (more specific than our `*:53`, so it won); `ps` showed `-C /opt/homebrew/etc/dnsmasq.conf` | `sudo brew services stop dnsmasq` (service was started as root) |
| Client Mac 4 not using team DNS | `curl: (6) Could not resolve host` while both DNS servers answered correctly | DNS (client resolver configuration) | `diagnose.py`: "this Mac's resolvers 8.8.8.8, 10.5.7.1 include NO team DNS server"; direct queries to both servers PASS | `client-dns.sh setup` |
| DNS servers changed 29 s apart | During that window the two resolvers gave different answers | DNS (inconsistent records) | `dns.sh point` timestamps 02:17:43 vs 02:18:12 | Change both servers together (in production: one primary + zone transfer / single source of truth) |
| Stray Backend A started on Mac 4 | Second process on 10.7.8.22:3001 | Application (deployment) | Ignored by nginx (upstream lists only 10.7.11.60:3001), found from the startup banner | Stopped; lesson: verify host before starting a service |
| Faculty fault | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

## 4. Learning summary (one paragraph per extension)

**A — Backup DNS.** Name resolution is a service with its own failure modes,
separate from the application. Once the client has two resolvers, losing
Mac 1 cost the client one slow request (≈2.2 s instead of ≈0.1 s: the
resolver waits for Mac 1, then asks Mac 3) and no errors. That only works if both resolvers serve
the **same** records, which is why both machines run one config and one
hosts file. A DNS failure shows up as "could not resolve host" before any
TCP packet is sent. An application failure shows up as a 502 *after* DNS,
TCP and TLS have all succeeded. The layer where the request stops tells you
which component failed.

**B — TTL.** TTL is a promise from the server: "you may reuse this answer for
N seconds without asking again." With TTL 30, changing the record on the
server is instant, but clients keep the old answer until their cached copy
expires. In our run the servers changed at 02:21:41 but the client kept the
old address until 02:21:56, and on the way back it held the old answer for
41 s. Flushing the client cache shortcuts this. In production this is why a migration starts by
*lowering* the TTL well ahead of time, and why the old server must keep
serving for at least one old-TTL after the change. A low TTL makes moves
fast but costs more queries. A high TTL is cheap but slow to change.

**C — Service isolation.** The edge exists so clients never need, or get,
direct access to the backends. pf on each backend turns that design rule
into an enforced one: TCP to the backend port is allowed only from the
edge's IP and dropped otherwise. The pf counters showed it working: 307
packets / 24 connections from the edge passed, and Kushal's direct attempt
was 3 dropped packets (SYN + 2 retransmissions) ending in a timeout, not a
refusal, so the client learns nothing about what is behind the edge. Because the rules were loaded from our
own file and `/etc/pf.conf` was never edited, rollback is one reload. Each
apply also saves a backup of the previous state. This is the local
equivalent of a cloud security group that allows the backend port only from
the load balancer's security group.

**D — HA failover.** nginx doesn't poll the backends. It learns from real
traffic: a refused or timed-out connection marks that backend down for
`fail_timeout`, and `proxy_next_upstream` re-sends the same request to the
other backend, so the client gets a 200 either way: 71 requests, 0 errors
while Backend A was down. Every ~15 s nginx let one real request test A
(log: `connect() failed (61: Connection refused)`), and when A came back it
rejoined at the very next request and round-robin resumed.
The remaining single point of failure is the **edge itself** (Mac 2): if it
dies, DNS still points every client at it. Removing that SPOF needs a second
edge plus a takeover mechanism: DNS cutover (E), a shared virtual IP with
VRRP/keepalived, or a managed multi-zone load balancer.

**E — DNS-based edge migration.** Moving traffic to the standby edge took
only a DNS change. Both edges have the same config and certificate, and TLS
validates the *name*, so the standby was trusted right away. The TTL made
the move gradual rather than instant: for up to 30 s, clients with a cached
answer kept using Mac 2 while fresh lookups went to Mac 4. Both edges served
in parallel during that window. That overlap is why the old edge was stopped
only after its access log went quiet. DNS cutover is simple and needs no
extra hardware. Its speed is limited by TTL (and by clients that ignore it),
so it suits planned migrations better than sudden failures.

**F — Troubleshooting.** ⟨Write this after the evaluation. Which fault you
got, what each layer check showed, where the request stopped, how you fixed
it.⟩
