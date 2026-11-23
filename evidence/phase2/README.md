# Phase 2 Evidence

Save captures and screenshots here with these names, so any item can be found
in 30 seconds during the evaluation. Tick each box once it's saved.

| ✓ | File | Extension | What it must show |
| :-: | :-- | :-- | :-- |
| ☐ | `A1_dns_primary_down_capture.pcapng` (+ `.png`) | A | query → 10.7.21.208, ICMP port unreachable, same query → 10.7.9.142, answer |
| ☐ | `A2_probe_with_primary_dns_down.png` | A | `dns.sh stop` on Mac 1 + `probe.sh` still 200 on Mac 4 |
| ☐ | `A3_backup_dnsmasq_log.png` | A | Mac 3 dnsmasq log answering the client |
| ☐ | `B1_dig_ttl30.png` | B | `dig` answer section with TTL 30 |
| ☐ | `B2_ttl_watch_cutover.png` | B | `ttl-watch.sh`: servers change, client-cache changes ≤ 30 s later |
| ☐ | `B3_flush_immediate.png` | B | after `client-dns.sh flush` the client switches immediately |
| ☐ | `C1_pf_rules_loaded.png` | C | `firewall.sh status` with counters |
| ☐ | `C2_edge_allowed_client_blocked.png` | C | Mac 2 `nc` succeeded / Mac 1 `nc` timed out |
| ☐ | `C3_client_syn_retransmissions.pcapng` | C | SYN, SYN retransmissions, no SYN-ACK |
| ☐ | `C4_rollback.png` | C | `firewall.sh rollback` + direct access works again |
| ☐ | `D1_probe_failover.png` | D | retried request `tried=[A, B]` → only B, summary 0 failures |
| ☐ | `D2_nginx_error_log.png` | D | `connect() failed (61)` + `temporarily disabled` |
| ☐ | `D3_edge_to_backend_RST.pcapng` | D | on Mac 2: SYN → Mac 3 answered with RST, next SYN → Mac 4 |
| ☐ | `D4_recovery.png` | D | A back in rotation after restart |
| ☐ | `D5_both_down_502.png` | D | JSON 502 + `/edge/health` 200 |
| ☐ | `E1_standby_health.png` | E | `X-Edge: standby-mac4`, no `-k` |
| ☐ | `E2_cutover_probe.png` | E | `==== edge address changed ====` line in `probe.sh` |
| ☐ | `E3_dns_answer_change.pcapng` | E | DNS answer 10.7.28.232 before, 10.7.22.224 after |
| ☐ | `F1_diagnose_output.png` | F | `diagnose.py` verdict during the faculty fault |
| ☐ | `X1_304_not_modified.png` | Phase 1 gap | `/api/data` with `If-None-Match` → 304 |

Commands for the 304 screenshot:
```bash
curl -si https://app.team1.test:8443/api/data | grep -iE 'HTTP/|etag|cache-control|x-backend'
curl -si -H 'If-None-Match: "<etag from above>"' https://app.team1.test:8443/api/data | grep -iE 'HTTP/|etag|x-backend'
```
Run the second command several times. Both backends answer `304`, because
both compute the same ETag from the same content.
