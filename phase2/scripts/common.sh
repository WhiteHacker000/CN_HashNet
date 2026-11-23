# Shared helpers for phase2 scripts (bash 3.2 compatible — macOS default bash).
# shellcheck shell=bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=../team.env
. "$REPO_ROOT/phase2/team.env"
# Optional override file (e.g. a 3-laptop role map): TEAM_ENV=path/to/other.env
if [ -n "${TEAM_ENV:-}" ]; then
    # shellcheck disable=SC1090
    . "$TEAM_ENV"
fi

if [ -t 1 ]; then
    C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'; C_BLU=$'\033[36m'; C_OFF=$'\033[0m'
else
    C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_OFF=""
fi

info() { printf '%s[*]%s %s\n' "$C_BLU" "$C_OFF" "$*"; }
ok()   { printf '%s[ok]%s %s\n' "$C_GRN" "$C_OFF" "$*"; }
warn() { printf '%s[!]%s %s\n' "$C_YEL" "$C_OFF" "$*" >&2; }
die()  { printf '%s[x]%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 1; }
run()  { printf '%s$ %s%s\n' "$C_YEL" "$*" "$C_OFF"; "$@"; }

is_macos() { [ "$(uname -s)" = "Darwin" ]; }
need_macos() { is_macos || die "This command only works on macOS."; }
ts() { date '+%H:%M:%S'; }
