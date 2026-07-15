#!/usr/bin/env bash
# pull.sh — fast-forward every BIC repo (meta, services, infra) to origin/main.
#
# The coworker story's update half: `make pull && make up` refreshes code,
# themes, and deps from the meta repo alone. Only fast-forwards — a repo with
# local commits or a non-main branch is reported and left untouched.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

printf '%s%sBIC pull%s ' "${C_BLD}" "${C_BLU}" "${C_RST}"
print_context

pull_one() { # <label> <dir>
  local label="$1" d="$2" branch before after
  if [ ! -d "${d}/.git" ]; then
    note "${label}: not cloned (${d}) — make bootstrap"
    return 0
  fi
  branch="$(git -C "${d}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  if [ "${branch}" != "main" ]; then
    warn "${label}: on branch '${branch}', not main — skipped (switch manually)"
    return 0
  fi
  before="$(git -C "${d}" rev-parse --short HEAD)"
  if do_run git -C "${d}" pull --ff-only -q origin main; then
    after="$(git -C "${d}" rev-parse --short HEAD)"
    if [ "${before}" = "${after}" ]; then
      ok "${label} @ ${after} (up to date)"
    else
      ok "${label} ${before} -> ${after}"
    fi
  else
    fail "${label}: cannot fast-forward (local commits or diverged)" \
         "cd ${d} && git status   # reconcile manually"
  fi
}

section "Repos"
pull_one BIC-meta "${BIC_META_DIR}"
for r in BIC-lab-service BIC-agent-service BIC-agent-portal BIC-shared-types mars_interface_mock BIC-chem-service; do
  pull_one "${r}" "$(repo_dir "${r}")"
done
pull_one BIC-infra "${INFRA_DIR}"

note "next: make up   # re-syncs deps/migrations/themes and restarts anything unhealthy"
printf '\n  %d ok  %d warn  %d red\n' "${BIC_OK}" "${BIC_WARN}" "${BIC_FAIL}"
[ "${BIC_FAIL}" = "0" ]
