#!/usr/bin/env bash
# Phase 2 edge (nginx) control.
#   Primary edge  (Mac 2): edge.sh <cmd> primary
#   Standby edge  (Mac 4): edge.sh <cmd> standby      (Extension E)
#
#   edge.sh test    <role>   syntax-check the config
#   edge.sh start   <role>   start nginx with nginx/phase2/edge-<role>.conf
#   edge.sh reload  <role>   re-read config without dropping connections
#   edge.sh stop    <role>   graceful stop
#   edge.sh status  <role>   running? + local /edge/health
#   edge.sh logs    <role>   follow access + error log (shows failover live)
#
# Stop the Phase 1 nginx first if it is still running on 8080/8443
# (brew services stop nginx   or   sudo nginx -s stop).
set -eu
. "$(dirname "$0")/common.sh"

cmd="${1:-}"; role="${2:-}"
case "$role" in primary|standby) ;; *) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;; esac

CONF="$REPO_ROOT/nginx/phase2/edge-$role.conf"
PIDFILE="/tmp/team1-edge-$role.pid"
CERT_DIR="$REPO_ROOT/nginx/phase2/certs"
command -v nginx >/dev/null || die "nginx not found (brew install nginx)"

check_certs() {
    for f in team1-server.crt team1-server.key; do
        [ -f "$CERT_DIR/$f" ] || die "Missing $CERT_DIR/$f — see nginx/phase2/certs/README.md"
    done
}

running_pid() {
    [ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE")" && kill -0 "$pid" 2>/dev/null && echo "$pid"
}

case "$cmd" in
test)   check_certs; run nginx -t -c "$CONF" ;;
start)
    check_certs
    if pid="$(running_pid)"; then die "edge $role already running (pid $pid)"; fi
    run nginx -t -c "$CONF"
    run nginx -c "$CONF"
    ok "edge $role started — https://$APP_HOST:$HTTPS_PORT  (logs: edge.sh logs $role)"
    ;;
reload)
    run nginx -t -c "$CONF"
    run nginx -s reload -c "$CONF"
    ok "edge $role reloaded"
    ;;
stop)
    if running_pid >/dev/null; then run nginx -s quit -c "$CONF"; ok "edge $role stopped"
    else warn "edge $role not running"; fi
    ;;
status)
    if pid="$(running_pid)"; then ok "edge $role running (master pid $pid)"; else warn "edge $role NOT running"; fi
    curl -s --max-time 3 "http://127.0.0.1:$HTTP_PORT/edge/health" -H "Host: $APP_HOST" || true
    ;;
logs)
    info "Following /tmp/team1-edge-$role-{access,error}.log (Ctrl+C to stop)"
    touch "/tmp/team1-edge-$role-access.log" "/tmp/team1-edge-$role-error.log" 2>/dev/null || true
    tail -n 5 -F "/tmp/team1-edge-$role-access.log" "/tmp/team1-edge-$role-error.log"
    ;;
*) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
