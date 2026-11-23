#!/usr/bin/env bash
# Send requests to the service BY NAME and show, per request, which edge and
# which backend answered. Used for load balancing (Phase 1 step 5), HA failover
# (Extension D) and edge cutover (Extension E).
#
#   probe.sh                    forever, every 0.5 s, GET /api/status over HTTPS
#   probe.sh -n 10              10 requests then a summary
#   probe.sh -i 1 -p /api/data  custom interval / path
#   probe.sh --http             use http://...:8080 instead of https://...:8443
#
# Each curl run is a new process, so every request does a fresh lookup through
# the macOS resolver (which honours the 30 s TTL) — exactly what you want to
# watch during a DNS cutover.
set -u
. "$(dirname "$0")/common.sh"

COUNT=0; INTERVAL=0.5; URLPATH=/api/status; SCHEME=https; PORT="$HTTPS_PORT"
while [ $# -gt 0 ]; do
    case "$1" in
        -n) COUNT="$2"; shift 2 ;;
        -i) INTERVAL="$2"; shift 2 ;;
        -p) URLPATH="$2"; shift 2 ;;
        --http) SCHEME=http; PORT="$HTTP_PORT"; shift ;;
        -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) die "unknown option $1" ;;
    esac
done
URL="$SCHEME://$APP_HOST:$PORT$URLPATH"

HDR="$(mktemp)"; ERR="$(mktemp)"
n=0; cA=0; cB=0; cErr=0; c5xx=0; last_ip=""

summary() {
    echo
    info "Summary for $URL"
    printf '      requests=%d  Backend-A=%d  Backend-B=%d  HTTP-5xx=%d  failed(no HTTP)=%d\n' \
        "$n" "$cA" "$cB" "$c5xx" "$cErr"
    rm -f "$HDR" "$ERR"
}
trap 'summary; exit 0' INT TERM

hdr() { grep -i "^$1:" "$HDR" | tail -1 | cut -d' ' -f2- | tr -d '\r'; }

layer_hint() {
    case "$1" in
        6)  echo "DNS: could not resolve $APP_HOST" ;;
        7)  echo "TCP: connection refused / host unreachable" ;;
        28) echo "TCP/HTTP: timed out (filtered port, host down, or slow upstream)" ;;
        35|60|58|51|77|83|90|91) echo "TLS: handshake / certificate verification failed" ;;
        52|56) echo "HTTP: edge closed the connection" ;;
        *)  echo "curl exit $1" ;;
    esac
}

info "Probing $URL  (Ctrl+C for summary)"
while :; do
    n=$((n + 1))
    : > "$HDR"
    rc=0
    out="$(curl -sS -o /dev/null -D "$HDR" --max-time 6 \
        -w '%{http_code} x%{remote_ip} %{time_total}' "$URL" 2>"$ERR")" || rc=$?
    # shellcheck disable=SC2086  # intentional word split into code/ip/time
    set -- $out
    code="${1:-000}"; ip="${2:-x}"; ip="${ip#x}"; t="${3:-?}"

    if [ -n "$ip" ] && [ -n "$last_ip" ] && [ "$ip" != "$last_ip" ]; then
        printf '%s======== edge address changed: %s -> %s ========%s\n' "$C_YEL" "$last_ip" "$ip" "$C_OFF"
    fi
    [ -n "$ip" ] && last_ip="$ip"

    if [ "$rc" -ne 0 ] && [ "$code" = "000" ]; then
        cErr=$((cErr + 1))
        printf '%s #%-4d %sFAIL%s  %s  (%s)\n' "$(ts)" "$n" "$C_RED" "$C_OFF" \
            "$(layer_hint "$rc")" "$(tr -d '\n' < "$ERR" | cut -c1-90)"
    else
        backend="$(hdr X-Backend)"; edge="$(hdr X-Edge)"; tried="$(hdr X-Debug-Upstream)"
        case "$backend" in *A) cA=$((cA + 1)) ;; *B) cB=$((cB + 1)) ;; esac
        color="$C_GRN"
        case "$code" in 5*) c5xx=$((c5xx + 1)); color="$C_RED" ;; 304) color="$C_BLU" ;; esac
        printf '%s #%-4d %s%s%s  edge=%s (%s)  backend=%-9s tried=[%s]  %ss\n' \
            "$(ts)" "$n" "$color" "$code" "$C_OFF" "$ip" "${edge:--}" "${backend:--}" "${tried:--}" "$t"
    fi

    if [ "$COUNT" -gt 0 ] && [ "$n" -ge "$COUNT" ]; then summary; exit 0; fi
    sleep "$INTERVAL"
done
