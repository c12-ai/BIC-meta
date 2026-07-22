#!/usr/bin/env bash
# gh-app-token.sh — mint a short-lived installation token for the c12-apex-dev
# GitHub App: the shared bot identity AI agents use for PRs, issues and other
# gh writes (shows up as c12-apex-dev[bot], cannot approve its own PRs).
#
# One-time setup per machine (full story: docs/agents/github-bot.md):
#   mkdir -p ~/.config/bic-v2/gh-app
#   <fetch private-key.pem from the team vault> -> ~/.config/bic-v2/gh-app/private-key.pem
#   chmod 600 ~/.config/bic-v2/gh-app/private-key.pem
# Nothing else: APP_ID is baked below and the installation id is auto-discovered.
#
# Usage:
#   gh-app-token.sh                  print a valid token (mints, or reuses cache)
#   gh-app-token.sh --env            print an eval-able `export GH_TOKEN=...`
#   gh-app-token.sh --check          mint + verify against GitHub, print identity
#   gh-app-token.sh --credential get git credential-helper protocol (push-as-bot,
#                                    optional — see the doc before wiring this)
#
# Tokens live 1 hour; a cache under ~/.cache/bic-v2/ is reused while it still
# has >5 min left, so calling this on every gh invocation is free.
set -euo pipefail

APP_ID="${BIC_GH_APP_ID:-4362356}"          # c12-apex-dev (org c12-ai)
KEY_FILE="${BIC_GH_APP_KEY:-$HOME/.config/bic-v2/gh-app/private-key.pem}"
CACHE_FILE="$HOME/.cache/bic-v2/gh-app-token.json"
API="https://api.github.com"

die() { echo "gh-app-token: $*" >&2; exit 1; }

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

json_get() { # <key> — read one string/number field from JSON on stdin
  python3 -c 'import json,sys; d=json.load(sys.stdin); v=d.get(sys.argv[1],""); print(v if v is not None else "")' "$1"
}

# ── cached token still fresh? ────────────────────────────────────────────────
cached_token() {
  [ -f "$CACHE_FILE" ] || return 1
  local tok exp now
  tok="$(json_get token < "$CACHE_FILE" 2>/dev/null)" || return 1
  exp="$(json_get expires_epoch < "$CACHE_FILE" 2>/dev/null)" || return 1
  now="$(date +%s)"
  [ -n "$tok" ] && [ -n "$exp" ] && [ "$now" -lt "$(( ${exp%.*} - 300 ))" ] || return 1
  printf '%s' "$tok"
}

# ── mint: JWT (RS256) -> discover installation -> installation token ─────────
mint() {
  [ -f "$KEY_FILE" ] || die "private key missing: $KEY_FILE
  -> fetch it from the team vault (see docs/agents/github-bot.md), chmod 600"

  local now header payload unsigned sig jwt
  now="$(date +%s)"
  header="$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)"
  payload="$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' "$((now - 60))" "$((now + 540))" "$APP_ID" | b64url)"
  unsigned="${header}.${payload}"
  sig="$(printf '%s' "$unsigned" | openssl dgst -sha256 -sign "$KEY_FILE" 2>/dev/null | b64url)" \
    || die "signing failed — is $KEY_FILE a valid RSA private key?"
  jwt="${unsigned}.${sig}"

  # Discover this app's installation on the org (no INSTALLATION_ID to configure).
  local inst_resp inst_id
  inst_resp="$(curl -sS -H "Authorization: Bearer $jwt" -H "Accept: application/vnd.github+json" \
    "$API/app/installations")" || die "GitHub unreachable"
  inst_id="$(printf '%s' "$inst_resp" | python3 -c '
import json,sys
d=json.load(sys.stdin)
if isinstance(d, dict):  # error object, not a list
    sys.exit("ERR:" + d.get("message","unknown error"))
print(d[0]["id"] if d else "")' 2>&1)" || true
  case "$inst_id" in
    ERR:*) die "JWT rejected (${inst_id#ERR:}) — wrong/rotated private key for app id $APP_ID?" ;;
    "")    die "app $APP_ID has no installation — install c12-apex-dev on the c12-ai org first" ;;
  esac

  local tok_resp token expires_epoch
  tok_resp="$(curl -sS -X POST -H "Authorization: Bearer $jwt" -H "Accept: application/vnd.github+json" \
    "$API/app/installations/${inst_id}/access_tokens")" || die "GitHub unreachable"
  token="$(printf '%s' "$tok_resp" | json_get token)"
  [ -n "$token" ] || die "token mint failed: $(printf '%s' "$tok_resp" | json_get message)"
  expires_epoch="$(( $(date +%s) + 3600 ))"

  mkdir -p "$(dirname "$CACHE_FILE")"
  ( umask 077; printf '{"token":"%s","expires_epoch":%d,"installation_id":%s}\n' \
      "$token" "$expires_epoch" "$inst_id" > "$CACHE_FILE" )
  printf '%s' "$token"
}

get_token() { cached_token || mint; }

# ── modes ────────────────────────────────────────────────────────────────────
case "${1:-}" in
  ""|--print)
    get_token; echo ;;
  --env)
    printf 'export GH_TOKEN=%s\n' "$(get_token)" ;;
  --check)
    tok="$(get_token)"
    repos="$(curl -sS -H "Authorization: Bearer $tok" -H "Accept: application/vnd.github+json" \
      "$API/installation/repositories?per_page=1" | json_get total_count)"
    echo "OK  identity: c12-apex-dev[bot]  (app id $APP_ID)"
    echo "    repos visible to the installation: ${repos:-?}"
    echo "    commit author line: c12-apex-dev[bot] <307868801+c12-apex-dev[bot]@users.noreply.github.com>" ;;
  --credential)
    # git credential-helper protocol; only `get` is answered.
    [ "${2:-}" = "get" ] || exit 0
    host=""; proto=""
    while IFS= read -r line; do
      [ -z "$line" ] && break
      case "$line" in
        host=*) host="${line#host=}" ;;
        protocol=*) proto="${line#protocol=}" ;;
      esac
    done
    if [ "$host" = "github.com" ] && [ "$proto" = "https" ]; then
      printf 'username=x-access-token\npassword=%s\n' "$(get_token)"
    fi ;;
  *)
    die "unknown flag: $1 (use --env | --check | --credential get)" ;;
esac
