# Troubleshooting Playbook — Extension F

The faculty will break one thing. You get marks for **method** even if the
fix isn't finished, so say every step out loud: *"I'm checking layer X
because…, I expect…, I see…, so the fault is / isn't here."*

## The method: follow the request, bottom-up through the dependencies

A request can only get as far as the first broken layer. Each layer below
depends on the one before it, so test them **in this order** and stop at the
first one that fails:

| # | Layer | Question | Manual command (client Mac) | Good result |
| :-- | :-- | :-- | :-- | :-- |
| 1 | DNS | Does the name resolve, to the **right** IP? | `dig app.team1.test` · `dig @10.7.21.208 app.team1.test` · `dig @10.7.9.142 app.team1.test` · `dscacheutil -q host -a name app.team1.test` | `10.7.28.232` everywhere |
| 2 | IP | Is that host reachable? | `ping -c 3 10.7.28.232` | replies (no reply alone isn't proof: ICMP can be blocked) |
| 3 | TCP | Does the port accept a connection? | `nc -vz -G 3 10.7.28.232 8443` | `succeeded` |
| 4 | TLS | Valid, trusted cert for this name? | `openssl s_client -connect 10.7.28.232:8443 -servername app.team1.test -CAfile tls/team1-ca.crt </dev/null \| grep -E 'Verify return\|subject\|issuer'` | `Verify return code: 0 (ok)` |
| 5 | HTTP edge | Is nginx itself OK? | `curl -i https://app.team1.test:8443/edge/health` | 200, `X-Edge` |
| 6 | HTTP app | Do the backends answer through it? | `curl -i https://app.team1.test:8443/api/status` (×4) | 200, A and B |
| 7 | Edge → backend | (on Mac 2) Can the edge reach each backend? | `curl -m 3 http://10.7.9.142:3001/health` · `curl -m 3 http://10.7.22.224:3002/health` · `tail /tmp/team1-edge-primary-error.log` | 200 / 200 |

`python3 phase2/scripts/diagnose.py` (add `--backends` on Mac 2) runs layers
1–7 in one go and names the first failing layer. Use it to find the fault
fast, then **prove it with the manual command for that layer**. The
examiners want to see you reason, not a script.

### Reading the error tells you the layer

| Symptom | Layer | Meaning |
| :-- | :-- | :-- |
| `curl: (6) Could not resolve host` | DNS | no answer for the name at all |
| Resolves, but to an unexpected IP | DNS | wrong record (DNS works, it's just wrong — "a directory, not a connection") |
| `dig @server` → `connection refused` | DNS service | host up, dnsmasq not listening (stopped) |
| `dig @server` → `timed out` | network / host | host down, wrong IP, or packets dropped |
| `curl: (7) … Connection refused` | TCP | host answered with RST: nothing listening on that port (nginx stopped / wrong port) |
| `curl: (28) … timed out` while connecting | TCP / IP | SYN unanswered: host down or firewall dropping |
| `curl: (60) SSL certificate problem` | TLS | name mismatch / expired / untrusted CA (`-v` tells which) |
| `curl: (35)` handshake failure | TLS | TLS on a non-TLS port (`https://…:8080`), protocol mismatch |
| `502 Bad Gateway` (JSON from edge) | HTTP upstream | edge fine; no backend reachable **from the edge** |
| 200, but only one backend ever answers | HTTP upstream | one backend down/unreachable; failover is hiding it |
| `404` / app error JSON | Application | network path is fine; wrong path or app bug |

---

## Practice drills (run on each other before the evaluation)

One person breaks something while the others look away. Everyone else
diagnoses using the table above, then the person who broke it explains what
they did. Restore after each drill (`phase2/README.md` §8).

| # | Fault to inject | How | What you'll see | First failing layer |
| :-- | :-- | :-- | :-- | :-- |
| 1 | Wrong DNS record | Mac 1+3: `dns.sh point 10.7.28.99` | `diagnose`: "NOT a known edge"; curl times out | DNS |
| 2 | DNS servers out of sync | Mac 1 only: `dns.sh point standby` | some clients reach primary, some standby; diagnose warns "DISAGREE" | DNS |
| 3 | Both resolvers down | `dns.sh stop` on Mac 1 and Mac 3, flush client | `Could not resolve host` | DNS |
| 4 | nginx stopped | Mac 2: `edge.sh stop primary` | `(7) Connection refused` | TCP |
| 5 | Edge port changed | Mac 2: change `listen 8443` → `8444`, `edge.sh reload primary` | `(7) Connection refused` on 8443; `nc -vz … 8444` works | TCP |
| 6 | Wrong cert on edge | point `ssl_certificate` at a cert for another name (make one with `openssl req -x509 -subj /CN=wrong.test …`) | `(60) SSL: no alternative certificate subject name matches` | TLS |
| 7 | Client doesn't trust CA | on a client: Keychain Access → Team1-Root-CA → Never Trust | `(60) unable to get local issuer certificate` | TLS |
| 8 | Backend bound to localhost | Mac 3: `BIND=127.0.0.1 python3 backend-a/server.py` | client: only Backend-B; Mac 2 `curl 10.7.9.142:3001` refused | Edge → backend |
| 9 | pf blocks the edge | Mac 3: edit `team1_edges` to a wrong IP in the rendered ruleset and `sudo pfctl -f` it | only Backend-B; from Mac 2 `curl` **times out** (not refused) | Edge → backend |
| 10 | Wrong upstream port | Mac 2: change `:3001` → `:3005` in upstream, reload | only Backend-B; error log `connect() failed (61)` to :3005 | Edge → backend (config) |
| 11 | Both backends down | Ctrl+C both | JSON 502 from edge, `/edge/health` still 200 | HTTP upstream |

Drills 8–10 look the same from the client (only one backend answers), but
they come from different causes. **Refused vs. timeout** and **the nginx
error log** tell them apart. Practise saying why.
