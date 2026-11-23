#!/usr/bin/env python3
"""
Extension F — layer-by-layer diagnosis of app.team1.test.

Walks the request path in the same order a real request does and stops
guessing: DNS -> IP -> TCP -> TLS -> HTTP (-> backends, when run on the edge).
For each layer it prints what it checked, what it saw, and a PASS/WARN/FAIL.
The verdict at the end names the FIRST failing layer and what usually causes it.

Usage (from the repo root on any Mac):
    python3 phase2/scripts/diagnose.py                 # from a client Mac
    python3 phase2/scripts/diagnose.py --backends      # on Mac 2: also test edge -> backends
    python3 phase2/scripts/diagnose.py --host api.team1.test --count 6

Only Python standard library is used (no dig needed: DNS queries are built by
hand, which also lets us tell "DNS server process stopped" (ICMP port
unreachable -> refused) apart from "DNS host unreachable" (timeout)).
"""
import argparse
import http.client
import os
import platform
import random
import re
import socket
import ssl
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
COLORS = {PASS: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m", SKIP: "\033[90m"}
USE_COLOR = sys.stdout.isatty()


def load_env():
    env = {}
    files = [os.path.join(REPO, "phase2", "team.env")]
    if os.environ.get("TEAM_ENV"):
        files.append(os.environ["TEAM_ENV"])
    for path in files:
        with open(path) as fh:
            for line in fh:
                m = re.match(r"\s*([A-Z0-9_]+)=(.*)$", line)
                if m:
                    env[m.group(1)] = m.group(2).split("#")[0].strip().strip('"')
    return env


# --------------------------------------------------------------------------- output
results = []


def report(layer, status, msg, hint=None):
    results.append((layer, status, msg, hint))
    tag = status
    if USE_COLOR:
        tag = COLORS[status] + status + "\033[0m"
    print("  [%s] %s" % (tag, msg))


def section(title):
    print("\n== %s" % title)


# --------------------------------------------------------------------------- DNS
def dns_query(server, name, port=53, timeout=2.0):
    """Return (status, ips, ttl, detail). status in ok|nxdomain|refused|timeout|error."""
    qid = random.randint(0, 0xFFFF)
    header = struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0)  # RD=1
    qname = b"".join(bytes([len(p)]) + p.encode() for p in name.rstrip(".").split(".")) + b"\0"
    packet = header + qname + struct.pack("!HH", 1, 1)  # A, IN
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.connect((server, port))
        s.send(packet)
        data = s.recv(1500)
    except ConnectionRefusedError:
        return "refused", [], None, "ICMP port unreachable: host is up but nothing listens on %d" % port
    except socket.timeout:
        return "timeout", [], None, "no reply in %.0fs: host down/unreachable or packets dropped" % timeout
    except OSError as exc:
        return "error", [], None, str(exc)
    finally:
        s.close()

    rid, flags, qd, an, _, _ = struct.unpack("!HHHHHH", data[:12])
    rcode = flags & 0xF
    if rid != qid:
        return "error", [], None, "mismatched DNS id"
    if rcode == 3:
        return "nxdomain", [], None, "NXDOMAIN (name does not exist on this server)"
    if rcode != 0:
        return "error", [], None, "rcode %d" % rcode

    def skip_name(off):
        while True:
            length = data[off]
            if length == 0:
                return off + 1
            if length & 0xC0 == 0xC0:
                return off + 2
            off += 1 + length

    off = 12
    for _ in range(qd):
        off = skip_name(off) + 4
    ips, ttl = [], None
    for _ in range(an):
        off = skip_name(off)
        rtype, _rclass, rttl, rdlen = struct.unpack("!HHIH", data[off:off + 10])
        off += 10
        if rtype == 1 and rdlen == 4:
            ips.append(socket.inet_ntoa(data[off:off + 4]))
            ttl = rttl
        off += rdlen
    if not ips:
        return "nxdomain", [], None, "no A record in answer"
    return "ok", ips, ttl, ""


def system_resolvers():
    if platform.system() != "Darwin":
        try:
            with open("/etc/resolv.conf") as fh:
                return [l.split()[1] for l in fh if l.startswith("nameserver")]
        except OSError:
            return []
    try:
        out = subprocess.run(["scutil", "--dns"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return []
    first = out.split("resolver #2")[0]
    return re.findall(r"nameserver\[\d+\]\s*:\s*(\S+)", first)


# --------------------------------------------------------------------------- HTTP helper
def http_get(ip, port, host, path, tls_ctx=None, timeout=6.0):
    """Raw HTTP/1.1 GET to ip:port with Host/SNI = host. Returns (status, headers, body)."""
    raw = socket.create_connection((ip, port), timeout=timeout)
    sock = tls_ctx.wrap_socket(raw, server_hostname=host) if tls_ctx else raw
    try:
        req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: team1-diagnose\r\n"
               "Connection: close\r\n\r\n" % (path, host))
        sock.sendall(req.encode())
        resp = http.client.HTTPResponse(sock)
        resp.begin()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        sock.close()


# --------------------------------------------------------------------------- main
def main():
    env = load_env()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--host", default=env.get("APP_HOST", "app.team1.test"))
    ap.add_argument("--port", type=int, default=int(env.get("HTTPS_PORT", 8443)))
    ap.add_argument("--path", default="/api/status")
    ap.add_argument("--count", type=int, default=4, help="requests used to check load balancing")
    ap.add_argument("--ca", default=os.path.join(REPO, env.get("CA_CERT", "tls/team1-ca.crt")))
    ap.add_argument("--dns-port", type=int, default=int(os.environ.get("DNS_PORT", 53)))
    ap.add_argument("--backends", action="store_true",
                    help="also test direct TCP/HTTP to each backend (run this on the edge, Mac 2)")
    args = ap.parse_args()

    edges = {env.get("EDGE_PRIMARY_IP"): "primary edge (Mac 2)",
             env.get("EDGE_STANDBY_IP"): "standby edge (Mac 4)"}
    dns_servers = [("primary", env.get("DNS_PRIMARY_IP")), ("backup", env.get("DNS_BACKUP_IP"))]

    print("Team 1 diagnosis for https://%s:%d%s   (%s, %s)"
          % (args.host, args.port, args.path, socket.gethostname(), time.strftime("%H:%M:%S")))

    # ---------------- Layer 1: DNS
    section("Layer 1 — DNS (application layer, UDP 53): does the NAME turn into the right IP?")
    resolvers = system_resolvers()
    team_dns = {ip for _, ip in dns_servers}
    if resolvers:
        if team_dns & set(resolvers):
            report("dns", PASS, "this Mac's resolvers: %s" % ", ".join(resolvers))
        else:
            report("dns", WARN, "this Mac's resolvers %s include NO team DNS server %s"
                   % (", ".join(resolvers), "/".join(sorted(team_dns))),
                   "client is not configured to use the team DNS: ./phase2/scripts/client-dns.sh setup")

    server_answers = {}
    for label, ip in dns_servers:
        server_answers[label] = (ip,) + dns_query(ip, args.host, args.dns_port)
    any_ok = any(v[1] == "ok" for v in server_answers.values())
    for label, (ip, st, ips, ttl, detail) in server_answers.items():
        if st == "ok":
            report("dns", PASS, "%-7s DNS %-15s answers %s (TTL %ss)" % (label, ip, ", ".join(ips), ttl))
        else:
            # One resolver down while the other answers = the redundancy is doing
            # its job (Extension A): warn. Both down = DNS service failure.
            report("dns", WARN if any_ok else FAIL,
                   "%-7s DNS %-15s %s: %s" % (label, ip, st.upper(), detail),
                   "dnsmasq on %s stopped or unreachable (dns.sh status on that Mac)" % ip)
    ok_sets = {tuple(v[2]) for v in server_answers.values() if v[1] == "ok"}
    if len(ok_sets) > 1:
        report("dns", WARN, "primary and backup DNS DISAGREE: %s" % " vs ".join(", ".join(x) for x in ok_sets),
               "records out of sync — run the same 'dns.sh point ...' on both DNS servers")

    try:
        t0 = time.time()
        infos = socket.getaddrinfo(args.host, args.port, socket.AF_INET, socket.SOCK_STREAM)
        edge_ip = infos[0][4][0]
        report("dns", PASS, "system resolver (what curl/browser use): %s -> %s  (%.0f ms)"
               % (args.host, edge_ip, (time.time() - t0) * 1000))
    except socket.gaierror as exc:
        report("dns", FAIL, "system resolver cannot resolve %s: %s" % (args.host, exc),
               "DNS layer: check resolvers on this Mac, then whether dnsmasq is running on Mac 1/Mac 3")
        return verdict()

    if edge_ip in edges:
        report("dns", PASS, "%s is the %s" % (edge_ip, edges[edge_ip]))
    else:
        report("dns", FAIL, "%s is NOT a known edge (%s)" % (edge_ip, ", ".join(k for k in edges if k)),
               "DNS answers successfully but with the WRONG address — fix dns/phase2/team1.hosts "
               "(dns.sh point primary) and flush client caches")
    server_ips = {ip for v in server_answers.values() if v[1] == "ok" for ip in v[2]}
    if server_ips and edge_ip not in server_ips:
        report("dns", WARN, "this Mac uses %s but the DNS servers now say %s -> stale client cache (TTL)"
               % (edge_ip, ", ".join(sorted(server_ips))),
               "wait for the 30 s TTL or run ./phase2/scripts/client-dns.sh flush")

    # ---------------- Layer 2: IP
    section("Layer 2 — IP (network layer): is the edge host reachable at all?")
    ping_cmd = ["ping", "-c", "2", edge_ip] if platform.system() == "Darwin" else ["ping", "-c", "2", "-W", "2", edge_ip]
    try:
        p = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=8)
        m = re.search(r"(\d+(?:\.\d+)?)% packet loss", p.stdout)
        loss = float(m.group(1)) if m else 100.0
        if loss < 100:
            report("ip", PASS, "ping %s: %.0f%% loss" % (edge_ip, loss))
        else:
            report("ip", WARN, "ping %s: no replies (ICMP may just be blocked — TCP test decides)" % edge_ip)
    except Exception as exc:
        report("ip", SKIP, "ping unavailable: %s" % exc)

    # ---------------- Layer 3: TCP
    section("Layer 3 — TCP (transport layer): does %s:%d accept a connection?" % (edge_ip, args.port))
    try:
        t0 = time.time()
        socket.create_connection((edge_ip, args.port), timeout=3).close()
        report("tcp", PASS, "3-way handshake to %s:%d completed in %.0f ms" % (edge_ip, args.port, (time.time() - t0) * 1000))
    except ConnectionRefusedError:
        report("tcp", FAIL, "connection REFUSED by %s:%d (host replied with RST)" % (edge_ip, args.port),
               "host is up but nothing listens on that port: nginx stopped, or wrong port in URL/config")
        return verdict()
    except (socket.timeout, OSError) as exc:
        report("tcp", FAIL, "no answer from %s:%d (%s)" % (edge_ip, args.port, exc),
               "SYN got no reply: host down, wrong IP from DNS, or a firewall silently dropping")
        return verdict()

    # ---------------- Layer 4: TLS
    section("Layer 4 — TLS: is the certificate valid for '%s' and trusted?" % args.host)
    ctx = ssl.create_default_context()
    if os.path.exists(args.ca):
        ctx = ssl.create_default_context(cafile=args.ca)
        ca_note = "trust anchor %s" % os.path.relpath(args.ca, REPO)
    else:
        ca_note = "system CAs only (team CA not found at %s — pass --ca)" % args.ca
        report("tls", WARN, ca_note, "copy the PUBLIC team1-ca.crt into tls/ (never the .key)")
    # Python 3.13+ enables strict X.509 checks that reject CA certs without a
    # keyUsage extension (what plain `openssl req -x509` produces). curl and
    # browsers accept them, so match their behaviour.
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    try:
        raw = socket.create_connection((edge_ip, args.port), timeout=5)
        tls = ctx.wrap_socket(raw, server_hostname=args.host)
        cert = tls.getpeercert()
        san = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
        issuer = dict(x[0] for x in cert.get("issuer", ())).get("commonName", "?")
        report("tls", PASS, "%s %s, cert SAN=%s, issuer=%s, expires %s (%s)"
               % (tls.version(), tls.cipher()[0], ",".join(san), issuer, cert.get("notAfter"), ca_note))
        tls.close()
    except ssl.SSLCertVerificationError as exc:
        msg = exc.verify_message or str(exc)
        hint = "certificate problem"
        if "expired" in msg:
            hint = "server certificate expired — reissue it (tls/README.md) and reload nginx"
        elif "Hostname mismatch" in msg or "doesn't match" in msg:
            hint = "certificate SAN does not include %s — wrong cert loaded on this edge" % args.host
        elif "local issuer" in msg or "self signed" in msg or "self-signed" in msg:
            hint = "certificate not signed by a CA this client trusts — install/trust team1-ca.crt"
        report("tls", FAIL, "certificate verification failed: %s" % msg, hint)
        return verdict()
    except ssl.SSLError as exc:
        report("tls", FAIL, "TLS handshake failed: %s" % exc,
               "port answers but does not speak TLS (http vs https port?) or protocol/cipher mismatch")
        return verdict()
    except OSError as exc:
        report("tls", FAIL, "connection dropped during TLS: %s" % exc)
        return verdict()

    # ---------------- Layer 5: HTTP
    section("Layer 5 — HTTP (application layer): does the edge answer, and do the backends?")
    try:
        st, h, _ = http_get(edge_ip, args.port, args.host, "/edge/health", ctx)
        if st == 200:
            report("http", PASS, "edge itself is alive: /edge/health -> 200, X-Edge=%s" % h.get("x-edge", "-"))
        else:
            report("http", WARN, "/edge/health -> %d (Phase 1 config without this location?)" % st)
    except Exception as exc:
        report("http", FAIL, "edge did not answer HTTP: %s" % exc)
        return verdict()

    seen, codes = [], []
    for _ in range(args.count):
        try:
            st, h, body = http_get(edge_ip, args.port, args.host, args.path, ctx)
        except Exception as exc:
            report("http", FAIL, "GET %s failed: %s" % (args.path, exc))
            return verdict()
        codes.append(st)
        seen.append(h.get("x-backend", "-"))
        tried = h.get("x-debug-upstream", "")
        if "," in tried:
            report("http", WARN, "request was retried: nginx tried [%s] statuses [%s]"
                   % (tried, h.get("x-debug-upstream-status", "")),
                   "a backend is failing; nginx is hiding it from clients (Extension D)")
    if all(c == 502 or c == 504 for c in codes):
        report("http", FAIL, "GET %s -> %s: edge OK but NO backend answered" % (args.path, codes[0]),
               "backends down or unreachable FROM THE EDGE (process stopped, pf rules, wrong upstream "
               "IP/port in nginx). Run this script with --backends on Mac 2")
    elif any(c >= 500 for c in codes):
        report("http", FAIL, "GET %s -> mixed statuses %s" % (args.path, codes))
    elif any(c >= 400 for c in codes):
        report("http", WARN, "GET %s -> %s (application-level error, network path is fine)" % (args.path, codes))
    else:
        distinct = sorted(set(seen))
        if len(distinct) >= 2:
            report("http", PASS, "%d x GET %s -> %s; load balanced across %s"
                   % (args.count, args.path, sorted(set(codes)), ", ".join(distinct)))
        else:
            report("http", WARN, "%d x GET %s -> 200 but ONLY %s answered" % (args.count, args.path, distinct[0]),
                   "service works through one backend; the other is down or marked failed (Extension D)")

    # ---------------- Layer 6: backends (from edge)
    if args.backends:
        section("Layer 6 — edge -> backends (run on Mac 2): can THIS host reach each backend?")
        for label, ip, port in (("A", env.get("BACKEND_A_IP"), int(env.get("BACKEND_A_PORT", 3001))),
                                ("B", env.get("BACKEND_B_IP"), int(env.get("BACKEND_B_PORT", 3002)))):
            try:
                st, h, _ = http_get(ip, port, args.host, "/health", None, timeout=3)
                report("backend", PASS if st == 200 else WARN,
                       "Backend %s %s:%d -> HTTP %d (X-Backend=%s)" % (label, ip, port, st, h.get("x-backend", "-")))
            except ConnectionRefusedError:
                report("backend", FAIL, "Backend %s %s:%d REFUSED" % (label, ip, port),
                       "backend process not running, or bound to 127.0.0.1 instead of 0.0.0.0")
            except (socket.timeout, OSError) as exc:
                report("backend", FAIL, "Backend %s %s:%d no answer (%s)" % (label, ip, port, exc),
                       "host down or pf on the backend drops this source — check firewall.sh status there")

    return verdict()


def verdict():
    print("\n== Verdict")
    fails = [r for r in results if r[1] == FAIL]
    warns = [r for r in results if r[1] == WARN]
    if not fails:
        print("  All layers OK." + ("  %d warning(s):" % len(warns) if warns else ""))
        for layer, _, msg, hint in warns:
            print("   - [%s] %s%s" % (layer, msg, ("\n       -> " + hint) if hint else ""))
        return 0
    layer, _, msg, hint = fails[0]
    print("  FIRST FAILING LAYER: %s" % layer.upper())
    print("   observed : %s" % msg)
    if hint:
        print("   likely   : %s" % hint)
    print("  (Layers below this one passed, so the fault is here or above — fix it and re-run.)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
