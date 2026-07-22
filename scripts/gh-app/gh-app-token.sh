#!/usr/bin/env bash
# gh-app-token.sh — mint a short-lived installation token for the c12-apex-dev
# GitHub App: the shared bot identity AI agents use for PRs, issues and other
# gh writes (shows up as c12-apex-dev[bot], cannot approve its own PRs).
#
# The private key lives ONLY on the mint host (aws-test) — laptops hold no
# secret at all. With no local key configured, this script pipes ITSELF over
# ssh to the mint host and runs there against the box's pem, returning just
# the 1-hour token (single source of truth, nothing to deploy on the box).
# Teammate prerequisite: working `ssh aws-test` (same access as deploys).
# BIC_GH_APP_KEY=<pem path> forces a local-file key source (admin/tests);
# BIC_GH_APP_SSH / BIC_GH_APP_REMOTE_KEY override the mint host / box pem path.
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
SSH_HOST="${BIC_GH_APP_SSH:-aws-test}"      # mint host holding the pem
REMOTE_KEY="${BIC_GH_APP_REMOTE_KEY:-\$HOME/.config/bic-v2/gh-app/private-key.pem}"
KEY_FILE="${BIC_GH_APP_KEY:-}"              # local-file key source (admin/tests) — skips ssh
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

cache_write() { # <token> [installation_id]
  mkdir -p "$(dirname "$CACHE_FILE")"
  ( umask 077; printf '{"token":"%s","expires_epoch":%d,"installation_id":%s}\n' \
      "$1" "$(( $(date +%s) + 3600 ))" "${2:-0}" > "$CACHE_FILE" )
}

# ── remote mint: pipe THIS script to the mint host, run against the box pem ──
# BIC_GH_APP_NO_CACHE=1 on the remote leg forces a fresh mint there, so the
# token we cache locally really has a full hour on it.
mint_remote() {
  local tok
  tok="$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" \
      "BIC_GH_APP_KEY=$REMOTE_KEY BIC_GH_APP_NO_CACHE=1 bash -s -- --print" \
      < "${BASH_SOURCE[0]}")" \
    || die "remote mint via ssh $SSH_HOST failed — box reachable? pem at $REMOTE_KEY on the box? (see docs/agents/github-bot.md)"
  [ -n "$tok" ] || die "remote mint on $SSH_HOST returned an empty token"
  cache_write "$tok"
  printf '%s' "$tok"
}

# ── local mint: JWT (RS256) -> discover installation -> installation token ───
mint_local() {
  [ -f "$KEY_FILE" ] || die "BIC_GH_APP_KEY points at a missing file: $KEY_FILE"
  local key_pem now header payload unsigned sig jwt
  key_pem="$(cat "$KEY_FILE")"
  now="$(date +%s)"
  header="$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)"
  payload="$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' "$((now - 60))" "$((now + 540))" "$APP_ID" | b64url)"
  unsigned="${header}.${payload}"
  sig="$(printf '%s' "$unsigned" | openssl dgst -sha256 -sign <(printf '%s\n' "$key_pem") 2>/dev/null | b64url)" \
    || die "signing failed — is the key a valid RSA private key?"
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

  local tok_resp token
  tok_resp="$(curl -sS -X POST -H "Authorization: Bearer $jwt" -H "Accept: application/vnd.github+json" \
    "$API/app/installations/${inst_id}/access_tokens")" || die "GitHub unreachable"
  token="$(printf '%s' "$tok_resp" | json_get token)"
  [ -n "$token" ] || die "token mint failed: $(printf '%s' "$tok_resp" | json_get message)"

  cache_write "$token" "$inst_id"
  printf '%s' "$token"
}

get_token() {
  if [ "${BIC_GH_APP_NO_CACHE:-0}" != "1" ]; then
    if cached_token; then return 0; fi
  fi
  if [ -n "$KEY_FILE" ]; then mint_local; else mint_remote; fi
}

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
