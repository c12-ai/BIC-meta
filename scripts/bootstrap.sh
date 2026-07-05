#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"

usage() {
  cat <<'USAGE'
Usage: scripts/bootstrap.sh <all|backend|portal|lab|shared>

Environment:
  DRY_RUN=1  Print clone/skip decisions without changing the filesystem.
USAGE
}

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q' "$1"
    shift
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

clone_if_missing() {
  local name="$1"
  local path="$2"
  local url="$3"

  if [[ -e "$path" ]]; then
    printf 'skip %s: %s already exists\n' "$name" "$path"
    return 0
  fi

  printf 'clone %s: %s -> %s\n' "$name" "$url" "$path"
  run git clone "$url" "$path"
}

bootstrap_backend() {
  clone_if_missing "backend" "BIC-agent-service" "git@github.com:c12-ai/BIC-agent-service.git"
}

bootstrap_portal() {
  clone_if_missing "portal" "BIC-agent-portal" "git@github.com:c12-ai/BIC-agent-portal.git"
}

bootstrap_lab() {
  clone_if_missing "lab" "BIC-lab-service" "git@github.com:c12-ai/BIC-lab-service.git"
}

bootstrap_shared() {
  clone_if_missing "shared" "BIC-shared-types" "git@github.com:c12-ai/BIC-shared-types.git"
}

target="${1:-}"

case "$target" in
  all)
    bootstrap_lab
    bootstrap_backend
    bootstrap_portal
    bootstrap_shared
    ;;
  backend)
    bootstrap_backend
    ;;
  portal)
    bootstrap_portal
    ;;
  lab)
    bootstrap_lab
    ;;
  shared)
    bootstrap_shared
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
