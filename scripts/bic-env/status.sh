#!/usr/bin/env bash
# status.sh — one-screen status of the six managed services.
# READ-ONLY. Columns: service : port : status : git sha.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

printf '%s%sBIC status%s   ' "${C_BLD}" "${C_BLU}" "${C_RST}"
print_context

printf '\n  %-9s %-7s %-9s %s\n' "SERVICE" "PORT" "STATUS" "GIT"
printf '  %-9s %-7s %-9s %s\n' "-------" "----" "------" "---"

while IFS='|' read -r name port repo url; do
  [ -n "${name}" ] || continue

  # --- status ---
  case "${name}" in
    mock)
      if pgrep -f 'mars-interface-mock' >/dev/null 2>&1; then st="UP"; else st="DOWN"; fi
      ;;
    keycloak)
      iss="$(http_body "${url}" | jq -r .issuer 2>/dev/null || true)"
      if [ -n "${iss}" ] && [ "${iss}" != "null" ]; then st="UP"; else st="DOWN"; fi
      ;;
    portal)
      read -r code ct <<EOF2
$(http_code_ct "${url}")
EOF2
      case "${code} ${ct}" in
        "200 "*javascript*) st="UP" ;;
        200*)               st="WHITE" ;;   # server up but page won't compile
        *)                  st="DOWN" ;;
      esac
      ;;
    *)
      if [ "$(http_code "${url}")" = "200" ]; then st="UP"; else st="DOWN"; fi
      ;;
  esac

  # --- git sha ---
  case "${name}" in
    keycloak) sha="$(container_on_port 18080)"; sha="${sha:-none}" ;;
    mock)     sha="$(git_sha "$(repo_dir "${repo}")")" ;;
    chem)     sha="$(git_sha "${repo}")" ;;                 # repo is CHEM_DIR (abs)
    *)        sha="$(git_sha "$(repo_dir "${repo}")")" ;;
  esac

  # --- colour by status ---
  case "${st}" in
    UP)    col="${C_GRN}" ;;
    WHITE) col="${C_YEL}" ;;
    *)     col="${C_RED}" ;;
  esac
  printf '  %-9s %-7s %s%-9s%s %s\n' "${name}" "${port}" "${col}" "${st}" "${C_RST}" "${sha}"
done <<EOF
$(services)
EOF

# Infra one-liner.
printf '\n  %sinfra:%s ' "${C_DIM}" "${C_RST}"
if docker_up; then
  while IFS='|' read -r name _ _; do
    [ -n "${name}" ] || continue
    if container_running "${name}"; then col="${C_GRN}"; mark="ok"; else col="${C_RED}"; mark="DOWN"; fi
    printf '%s=%s ' "${name}" "${col}${mark}${C_RST}"
  done <<EOF
$(infra_containers)
EOF
  printf '\n'
else
  printf '%sdocker daemon DOWN%s\n' "${C_RED}" "${C_RST}"
fi

printf '\n  %sdetail: make doctor   ·   troubleshooting: ops/run-latest-2026-07-10.md%s\n' "${C_DIM}" "${C_RST}"
