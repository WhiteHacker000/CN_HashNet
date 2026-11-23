#!/usr/bin/env bash
# Extension B / E — watch DNS caching and TTL expiry from a CLIENT Mac.
#
#   ttl-watch.sh [interval-seconds]     (default 2)
#
# Every tick prints three views of app.team1.test side by side:
#   client-cache : what THIS Mac's resolver (mDNSResponder) returns — this is
#                  what curl / Safari / Chrome actually use; it is cached for TTL s
#   primary/backup : what each DNS server answers right now, with the TTL it sends
# After "dns.sh point ..." on the servers, primary/backup change at once while
# client-cache keeps the old IP until the TTL runs out (or client-dns.sh flush).
set -u
. "$(dirname "$0")/common.sh"
INTERVAL="${1:-2}"

client_answer() {
    if is_macos; then
        dscacheutil -q host -a name "$APP_HOST" 2>/dev/null | awk '/^ip_address:/{print $2; exit}'
    else
        getent ahostsv4 "$APP_HOST" 2>/dev/null | awk '{print $1; exit}'
    fi
}

server_answer() {
    # prints "IP(ttl=N)" or DOWN
    a="$(dig @"$1" ${DNS_PORT:+-p "$DNS_PORT"} +time=1 +tries=1 +noall +answer "$APP_HOST" A 2>/dev/null \
        | awk '$4=="A"{print $5"(ttl="$2")"; exit}')"
    echo "${a:-DOWN/no-answer}"
}

command -v dig >/dev/null || die "dig not found"
info "Watching $APP_HOST every ${INTERVAL}s — Ctrl+C to stop"
printf '%-9s %-18s %-26s %-26s\n' TIME client-cache "primary $DNS_PRIMARY_IP" "backup $DNS_BACKUP_IP"
prev=""
while :; do
    c="$(client_answer)"; c="${c:-unresolved}"
    line="$(printf '%-9s %-18s %-26s %-26s' "$(ts)" "$c" "$(server_answer "$DNS_PRIMARY_IP")" "$(server_answer "$DNS_BACKUP_IP")")"
    if [ -n "$prev" ] && [ "$c" != "$prev" ]; then
        printf '%s%s   <-- client now uses %s%s\n' "$C_YEL" "$line" "$c" "$C_OFF"
    else
        echo "$line"
    fi
    prev="$c"
    sleep "$INTERVAL"
done
