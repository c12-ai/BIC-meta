#!/usr/bin/env bash
# BIC V2 field bench reset — run ON the field box (orin / a1), package-relative.
#
#   ~/bic-v2/scripts/reset.sh --test          # full reset to the canonical test dataset
#   ~/bic-v2/scripts/reset.sh --demo          # full reset to the captured demo snapshot
#   ~/bic-v2/scripts/reset.sh --demo lab      # lab only
#   ~/bic-v2/scripts/reset.sh --test be       # BE only
#
# The dataset flag is REQUIRED (no default — same philosophy as the stage
# model): --test = canonical seed / schema-only empty; --demo = the captured
# bench snapshot baked into each service image (see each repo's
# scripts/capture_demo_snapshot.py).
#
# BE ``POST /reset`` is the documented no-auth dev endpoint (truncates every
# public-schema table, restores the selected dataset, purges the lab
# task-status queue/DLQ). Lab enforces Bearer JWT on all non-health routes
# since lab #112, so the lab step first mints a service-account token
# (client-credentials, bic-agent-service) from the on-box Keycloak. Secrets
# are read from the field .env and never echoed.
#
# --demo extra (BE leg): the snapshot's sessions belong to the CAPTURE
# site's Keycloak user ids, which differ from this realm's — without a grant
# no field login could see the demo session. After the restore we INSERT
# collaborator memberships for every user in this box's realm (captured
# rows keep their original attribution; ON CONFLICT keeps re-runs safe).
#
# Order is BE → lab on purpose: truncate/purge the agent side first, then
# re-seed lab data (which also sends the robot reset command over MQ).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$HERE/../.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found (run deploy.sh init-env first)" >&2; exit 1; }

getk() { { grep -m1 "^$1=" "$ENV_FILE" || true; } | cut -d= -f2-; }
BE_PORT="$(getk BE_PORT)";             BE_PORT="${BE_PORT:-8800}"
LAB_PORT="$(getk LAB_PORT)";           LAB_PORT="${LAB_PORT:-8192}"
KEYCLOAK_PORT="$(getk KEYCLOAK_PORT)"; KEYCLOAK_PORT="${KEYCLOAK_PORT:-18080}"
ROBOT_ID="$(getk MOCK_ROBOT_ID)";      ROBOT_ID="${ROBOT_ID:-talos.001}"
PG_CONTAINER="$(getk PG_CONTAINER)";   PG_CONTAINER="${PG_CONTAINER:-bic-postgres}"
KC_CONTAINER="$(getk KC_CONTAINER_NAME)"; KC_CONTAINER="${KC_CONTAINER:-bic-keycloak}"

GREEN=$'\033[32m'; RED=$'\033[31m'; NC=$'\033[0m'
ok()  { echo "${GREEN}  ✓${NC} $*"; }
die() { echo "${RED}  ✗ $*${NC}" >&2; exit 1; }

usage() { die "usage: reset.sh --test|--demo [all|be|lab]"; }

DATASET=""; SCOPE="all"
for arg in "$@"; do
  case "$arg" in
    --test) DATASET="test";;
    --demo) DATASET="demo";;
    all|be|lab) SCOPE="$arg";;
    *) usage;;
  esac
done
[ -n "$DATASET" ] || usage

if [ "$SCOPE" != lab ]; then
  body="$(curl -s --max-time 120 -X POST "http://localhost:${BE_PORT}/reset" \
        -H 'Content-Type: application/json' --data-raw "{\"dataset\": \"${DATASET}\"}")" \
    || die "BE reset: request failed (is agent-service up on :${BE_PORT}?)"
  echo "$body" | grep -q '"status": *"ok"\|"status":"ok"' \
    || die "BE reset: $(echo "$body" | head -c 300)"
  summary="$(echo "$body" | python3 -c 'import json,sys
d=json.load(sys.stdin)
r=d.get("restored_rows") or {}
t=len(d.get("truncated_tables") or [])
print(str(t) + " tables truncated, " + str(sum(r.values())) + " rows restored, MQ purged")' 2>/dev/null || echo done)"
  ok "BE reset (${DATASET}): ${summary}"

  if [ "$DATASET" = demo ]; then
    # Grant every realm user access to the restored demo sessions (see header).
    ADMIN_USER="$(getk KEYCLOAK_ADMIN)"; ADMIN_PASS="$(getk KEYCLOAK_ADMIN_PASSWORD)"
    docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh config credentials \
      --server http://localhost:8080 --realm master --user "$ADMIN_USER" --password "$ADMIN_PASS" \
      >/dev/null 2>&1 || die "demo grant: keycloak admin login failed"
    REALM_SUBS="$(docker exec "$KC_CONTAINER" /opt/keycloak/bin/kcadm.sh get users -r bic \
      --fields id --format csv --noquotes 2>/dev/null)"
    [ -n "$REALM_SUBS" ] || die "demo grant: no users found in realm bic"
    granted=0
    for sub in $REALM_SUBS; do
      docker exec "$PG_CONTAINER" psql -U postgres -d talos_agent_db -qAt -c \
        "INSERT INTO session_members (session_id, user_id, role)
         SELECT session_id, '${sub}', 'collaborator' FROM sessions
         ON CONFLICT (session_id, user_id) DO NOTHING;" >/dev/null \
        || die "demo grant: membership insert failed for ${sub}"
      granted=$((granted + 1))
    done
    ok "demo grant: ${granted} realm user(s) granted collaborator access to the demo sessions"
  fi
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
  code="$(curl -s -o /tmp/bic-lab-reset.json -w '%{http_code}' --max-time 120 \
        -X POST "http://127.0.0.1:${LAB_PORT}/admin/reset-to-test-data" \
        -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
        --data-raw "{\"robot_id\": \"${ROBOT_ID}\", \"dataset\": \"${DATASET}\"}")"
  [ "$code" = 200 ] || die "lab reset: HTTP $code — $(head -c 200 /tmp/bic-lab-reset.json 2>/dev/null)"
  ok "lab reset (${DATASET}): HTTP 200 $(head -c 120 /tmp/bic-lab-reset.json 2>/dev/null)"
  rm -f /tmp/bic-lab-reset.json
fi

ok "reset done (${DATASET}, ${SCOPE})"
