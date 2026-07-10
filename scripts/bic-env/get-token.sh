#!/usr/bin/env bash
# get-token.sh — print a Keycloak bearer token for manual lab-service calls
# (curl / Apifox). Uses the bic-agent-service client-credentials service
# account, so it works headlessly on any seeded bench.
#
#   curl --noproxy '*' -H "Authorization: Bearer $(scripts/bic-env/get-token.sh)" \
#     http://localhost:8192/preparations/racks
#
# Token lifetime is the realm default (300 s) — re-run when it expires.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

resp="$(curl --noproxy '*' -sf \
  -d grant_type=client_credentials \
  -d "client_id=${KC_SERVICE_CLIENT}" \
  -d "client_secret=${KC_SERVICE_CLIENT_SECRET}" \
  "http://localhost:18080/realms/${KC_REALM}/protocol/openid-connect/token")" || {
  printf 'get-token: token grant failed — is keycloak up and the %s client seeded? (make up)\n' \
    "${KC_SERVICE_CLIENT}" >&2
  exit 1
}

printf '%s\n' "${resp}" | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
