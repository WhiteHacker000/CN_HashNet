# Phase 2 Final Report — Team 1: Harden, Recover, Troubleshoot

> **Before submitting:** fill every `⟨…⟩` with what you actually observed on the
> four Macs (times, counts, screenshot names). The explanations are complete,
> but the results must come from your own runs.

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

| # | Test | Expected | Observed | Evidence file |
| :-- | :-- | :-- | :-- | :-- |
| A1 | Stop dnsmasq on Mac 1, resolve from Mac 4 | name still resolves via 10.7.11.60 | ⟨…⟩ | ⟨…⟩ |
| A2 | `dig @10.7.11.54` while stopped | connection refused (ICMP port unreachable) | ⟨…⟩ | ⟨…⟩ |
| B1 | `dig` TTL field | 30 | ⟨…⟩ | ⟨…⟩ |
| B2 | Record changed at ⟨time⟩; client switched at ⟨time⟩ | ≤ 30 s later | ⟨Δ = … s⟩ | ⟨…⟩ |
| B3 | Flush client cache after change | immediate switch | ⟨…⟩ | ⟨…⟩ |
| C1 | Mac 2 → 10.7.11.60:3001 | connects | ⟨…⟩ | ⟨…⟩ |
| C2 | Mac 1 → 10.7.11.60:3001 / 10.7.8.22:3002 | timeout | ⟨…⟩ | ⟨…⟩ |
| C3 | Service via edge with pf active | 200, both backends | ⟨…⟩ | ⟨…⟩ |
| C4 | Rollback restores direct access | connects | ⟨…⟩ | ⟨…⟩ |
| D1 | Backend A stopped during `probe.sh` | 0 failed requests, 1 retried, then only B | ⟨n requests, … failed⟩ | ⟨…⟩ |
| D2 | Backend A restarted | back in rotation within ≤ 10 s | ⟨… s⟩ | ⟨…⟩ |
| D3 | Both backends stopped | JSON 502 from edge, `/edge/health` 200 | ⟨…⟩ | ⟨…⟩ |
| E1 | DNS switched to standby at ⟨time⟩ | cached clients stay on Mac 2 ≤ 30 s, new lookups hit Mac 4 | ⟨…⟩ | ⟨…⟩ |
| E2 | Standby TLS without `-k` | valid (cert is for the name) | ⟨…⟩ | ⟨…⟩ |

## 3. Troubleshooting findings

Practice drills (see `docs/Troubleshooting-Playbook.md`) and the faculty fault:

| Fault | Symptom seen | Layer identified | How we proved it | Fix |
| :-- | :-- | :-- | :-- | :-- |
| ⟨faculty fault⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| ⟨drill⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

## 4. Learning summary (one paragraph per extension)

**A — Backup DNS.** Name resolution is a service with its own failure modes,
separate from the application. Once the client has two resolvers, losing
Mac 1 costs only a short retry: the resolver gets an ICMP port-unreachable
from Mac 1 and asks Mac 3 instead. That only works if both resolvers serve
the **same** records, which is why both machines run one config and one
hosts file. A DNS failure shows up as "could not resolve host" before any
TCP packet is sent. An application failure shows up as a 502 *after* DNS,
TCP and TLS have all succeeded. The layer where the request stops tells you
which component failed.

**B — TTL.** TTL is a promise from the server: "you may reuse this answer for
N seconds without asking again." With TTL 30, changing the record on the
server is instant, but clients keep the old answer until their cached copy
expires. We watched this happen in `ttl-watch.sh`, and saw that flushing the
client cache shortcuts it. In production this is why a migration starts by
*lowering* the TTL well ahead of time, and why the old server must keep
serving for at least one old-TTL after the change. A low TTL makes moves
fast but costs more queries. A high TTL is cheap but slow to change.

**C — Service isolation.** The edge exists so clients never need, or get,
direct access to the backends. pf on each backend turns that design rule
into an enforced one: TCP to the backend port is allowed only from the
edge's IP and dropped otherwise. A dropped SYN gives the client a timeout,
not a refusal, so it learns nothing. Because the rules were loaded from our
own file and `/etc/pf.conf` was never edited, rollback is one reload. Each
apply also saves a backup of the previous state. This is the local
equivalent of a cloud security group that allows the backend port only from
the load balancer's security group.

**D — HA failover.** nginx doesn't poll the backends. It learns from real
traffic: a refused or timed-out connection marks that backend down for
`fail_timeout`, and `proxy_next_upstream` re-sends the same request to the
other backend, so the client gets a 200 either way. When Backend A came back,
nginx let one request through after the 10 s window and resumed round-robin.
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
