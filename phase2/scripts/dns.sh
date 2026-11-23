#!/usr/bin/env bash
# Phase 2 DNS control — run on Mac 1 (primary) AND Mac 3 (backup).
#
#   dns.sh start                 run dnsmasq in the foreground (query log on screen)
#   dns.sh stop                  stop it (Extension A: "primary DNS failure")
#   dns.sh status                running? what records are we serving?
#   dns.sh point primary         app/api.team1.test -> primary edge (Mac 2)
#   dns.sh point standby         app/api.team1.test -> standby edge (Mac 4)  (Extension E)
#   dns.sh point 10.7.x.y        any IP                                      (Extension B)
#
# "point" rewrites dns/phase2/team1.hosts and sends SIGHUP to dnsmasq, which
# re-reads the file and empties its own cache. No restart, so it is instant on
# this server; clients still hold the OLD answer until their TTL (30 s) runs out.
# Run "point" on BOTH DNS servers, otherwise primary and backup disagree.
set -eu
. "$(dirname "$0")/common.sh"

CONF="$REPO_ROOT/dns/phase2/dnsmasq-phase2.conf"
HOSTS="$REPO_ROOT/dns/phase2/team1.hosts"
PIDFILE="${DNS_PIDFILE:-/tmp/team1-dnsmasq.pid}"
# dnsmasq drops root privileges to "nobody" after starting, and "nobody" cannot
# read files under ~/Documents. So it serves a world-readable copy in /tmp;
# the repo file stays the version-controlled source.
RUNTIME_HOSTS="${DNS_RUNTIME_HOSTS:-/tmp/team1-dns.hosts}"
DNS_PORT="${DNS_PORT:-53}"
SUDO="sudo"; [ "$(id -u)" -eq 0 ] && SUDO=""

dns_pid() {
    [ -f "$PIDFILE" ] || return 1
    pid="$(cat "$PIDFILE" 2>/dev/null)"
    [ -n "$pid" ] && $SUDO kill -0 "$pid" 2>/dev/null && echo "$pid"
}

current_ip() { awk '$2=="'"$APP_HOST"'"{print $1}' "$HOSTS"; }

publish_hosts() {
    cp "$HOSTS" "$RUNTIME_HOSTS.new" && chmod 644 "$RUNTIME_HOSTS.new" && mv "$RUNTIME_HOSTS.new" "$RUNTIME_HOSTS"
}

case "${1:-}" in
start)
    # full path: sudo resets PATH and may not see /opt/homebrew/sbin
    DNSMASQ="$(command -v dnsmasq)" || die "dnsmasq not found (brew install dnsmasq)"
    if pid="$(dns_pid)"; then die "dnsmasq already running (pid $pid). Use: dns.sh stop"; fi
    info "Serving $APP_HOST -> $(current_ip) with TTL 30 s on port $DNS_PORT"
    info "Query log follows. Ctrl+C (or 'dns.sh stop' in another terminal) to stop."
    publish_hosts
    # -k: stay in foreground but still write the pid file (needed for stop / SIGHUP)
    exec $SUDO "$DNSMASQ" -k --conf-file="$CONF" --addn-hosts="$RUNTIME_HOSTS" \
        --pid-file="$PIDFILE" --port="$DNS_PORT"
    ;;
stop)
    if pid="$(dns_pid)"; then
        run $SUDO kill "$pid"
        ok "dnsmasq stopped at $(ts) — this resolver no longer answers on port $DNS_PORT"
    else
        warn "dnsmasq is not running (no live pid in $PIDFILE)"
    fi
    ;;
status)
    if pid="$(dns_pid)"; then ok "dnsmasq running (pid $pid)"; else warn "dnsmasq NOT running"; fi
    info "Records in $HOSTS:"
    grep -v '^#' "$HOSTS" | sed 's/^/      /'
    if command -v dig >/dev/null; then
        info "Live answer from this server:"
        dig @127.0.0.1 -p "$DNS_PORT" +time=2 +tries=1 +noall +answer "$APP_HOST" | sed 's/^/      /' || true
    fi
    ;;
point)
    target="${2:-}"
    case "$target" in
        primary) ip="$EDGE_PRIMARY_IP" ;;
        standby) ip="$EDGE_STANDBY_IP" ;;
        *.*.*.*) ip="$target" ;;
        *) die "usage: dns.sh point <primary|standby|IPv4>" ;;
    esac
    old="$(current_ip)"
    tmp="$HOSTS.tmp.$$"
    {
        echo "# Team 1 project records (served by dnsmasq with TTL = local-ttl = 30 s)"
        echo "# Last changed $(date '+%Y-%m-%d %H:%M:%S') by dns.sh point $target (was $old)"
        echo "# Change with:  ./phase2/scripts/dns.sh point <primary|standby|IP>"
        echo "$ip  $APP_HOST"
        echo "$ip  $API_HOST"
    } > "$tmp"
    mv "$tmp" "$HOSTS"
    publish_hosts
    if pid="$(dns_pid)"; then
        $SUDO kill -HUP "$pid"
        ok "$(ts)  $APP_HOST: $old -> $ip  (dnsmasq reloaded, pid $pid)"
    else
        warn "$(ts)  hosts file updated ($old -> $ip) but dnsmasq is not running here"
    fi
    warn "Remember to run the same 'dns.sh point $target' on the OTHER DNS server."
    info "Clients that resolved in the last 30 s keep using $old until their cache expires."
    ;;
*)
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
