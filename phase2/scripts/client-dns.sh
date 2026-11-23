#!/usr/bin/env bash
# Client-side DNS settings for Extensions A, B and E (run on the test client Macs).
#
#   client-dns.sh setup     resolvers = primary (Mac 1) THEN backup (Mac 3); saves old settings
#   client-dns.sh show      what this Mac is actually using (scutil --dns)
#   client-dns.sh flush     flush macOS DNS cache (Extension B "manual flush")
#   client-dns.sh restore   put back the DNS servers saved by 'setup'
set -eu
. "$(dirname "$0")/common.sh"
need_macos

SAVE="$HOME/.team1-dns-backup"

flush() {
    run sudo dscacheutil -flushcache
    run sudo killall -HUP mDNSResponder
    ok "$(ts) macOS DNS cache flushed"
}

case "${1:-}" in
setup)
    if [ ! -f "$SAVE" ]; then
        networksetup -getdnsservers "$NET_SERVICE" > "$SAVE"
        info "Saved previous DNS servers to $SAVE"
    fi
    run sudo networksetup -setdnsservers "$NET_SERVICE" "$DNS_PRIMARY_IP" "$DNS_BACKUP_IP"
    flush
    ok "$NET_SERVICE now uses $DNS_PRIMARY_IP (primary) and $DNS_BACKUP_IP (backup)"
    ;;
show)
    run networksetup -getdnsservers "$NET_SERVICE"
    info "Resolver order macOS is really using:"
    scutil --dns | awk '/^resolver #1/{f=1} f&&/nameserver/{print "      "$0} /^resolver #2/{exit}'
    ;;
flush) flush ;;
restore)
    [ -f "$SAVE" ] || die "No saved settings ($SAVE). Nothing to restore."
    if grep -qi "aren't any" "$SAVE"; then
        run sudo networksetup -setdnsservers "$NET_SERVICE" Empty
    else
        # shellcheck disable=SC2046
        run sudo networksetup -setdnsservers "$NET_SERVICE" $(cat "$SAVE")
    fi
    rm -f "$SAVE"
    flush
    ok "DNS servers restored"
    ;;
*) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
