#!/usr/bin/env bash
# BIC V2 field bench reset — run ON the field box (orin / a1), package-relative.
#
#   ~/bic-v2/scripts/reset.sh          # full reset: BE (DB truncate + MQ purge) then lab (re-seed test data)
#   ~/bic-v2/scripts/reset.sh lab      # lab only
#   ~/bic-v2/scripts/reset.sh be       # BE only
#
# BE ``POST /reset`` is the documented no-auth dev endpoint (truncates every
# public-schema table + purges the lab task-status queue/DLQ). Lab enforces
# Bearer JWT on all non-health routes since lab #112, so the lab step first
# mints a service-account token (client-credentials, bic-agent-service) from
# the on-box Keycloak. Secrets are read from the field .env and never echoed.
#
# Order is BE → lab on purpose: truncate/purge the agent side first, then
# re-seed lab test data (which also sends the robot reset command over MQ).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$HERE/../.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found (run deploy.sh init-env first)" >&2; exit 1; }

getk() { { grep -m1 "^$1=" "$ENV_FILE" || true; } | cut -d= -f2-; }
BE_PORT="$(getk BE_PORT)";             BE_PORT="${BE_PORT:-8800}"
LAB_PORT="$(getk LAB_PORT)";           LAB_PORT="${LAB_PORT:-8192}"
KEYCLOAK_PORT="$(getk KEYCLOAK_PORT)"; KEYCLOAK_PORT="${KEYCLOAK_PORT:-18080}"
ROBOT_ID="$(getk MOCK_ROBOT_ID)";      ROBOT_ID="${ROBOT_ID:-talos.001}"

GREEN=$'\033[32m'; RED=$'\033[31m'; NC=$'\033[0m'
ok()  { echo "${GREEN}  ✓${NC} $*"; }
die() { echo "${RED}  ✗ $*${NC}" >&2; exit 1; }

SCOPE="${1:-all}"
case "$SCOPE" in all|be|lab) ;; *) die "usage: reset.sh [all|be|lab]";; esac

if [ "$SCOPE" != lab ]; then
  body="$(curl -s --max-time 60 -X POST "http://localhost:${BE_PORT}/reset")" \
    || die "BE reset: request failed (is agent-service up on :${BE_PORT}?)"
  echo "$body" | grep -q '"status"' || die "BE reset: unexpected response: $(echo "$body" | head -c 200)"
  tables="$(echo "$body" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("truncated_tables",[])))' 2>/dev/null || echo '?')"
  ok "BE reset: ${tables} tables truncated, MQ purged"
fi

if [ "$SCOPE" != be ]; then
  SEC="$(getk BIC_AGENT_SERVICE_CLIENT_SECRET)"
  [ -n "$SEC" ] && [ "$SEC" != "__FILL_ME__" ] || die "BIC_AGENT_SERVICE_CLIENT_SECRET missing in $ENV_FILE"
  TOK="$(curl -s --max-time 15 -X POST \
        "http://localhost:${KEYCLOAK_PORT}/realms/bic/protocol/openid-connect/token" \
        -d grant_type=client_credentials -d client_id=bic-agent-service \
        --data-urlencode "client_secret=$SEC" \
        | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')" \
    || die "lab reset: token request failed (keycloak up on :${KEYCLOAK_PORT}?)"
  [ -n "$TOK" ] || die "lab reset: no access_token (client secret vs realm client mismatch?)"
  code="$(curl -s -o /tmp/bic-lab-reset.json -w '%{http_code}' --max-time 60 \
        -X POST "http://127.0.0.1:${LAB_PORT}/admin/reset-to-test-data" \
        -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
        --data-raw "{\"robot_id\": \"${ROBOT_ID}\"}")"
  [ "$code" = 200 ] || die "lab reset: HTTP $code — $(head -c 200 /tmp/bic-lab-reset.json 2>/dev/null)"
  ok "lab reset: HTTP 200 $(head -c 120 /tmp/bic-lab-reset.json 2>/dev/null)"
  rm -f /tmp/bic-lab-reset.json
fi

ok "reset done (${SCOPE})"
