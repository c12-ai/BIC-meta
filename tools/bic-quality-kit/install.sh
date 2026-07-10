#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$KIT_DIR/../.." && pwd)"
SKILL_NAME="bic-quality-guan-ping-ce"
SOURCE_DIR="$KIT_DIR/skill/$SKILL_NAME"
BACKUP_STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP_ROOT="${BIC_QUALITY_BACKUP_ROOT:-$ROOT_DIR/.trellis/.runtime/skill-backups/$SKILL_NAME/$BACKUP_STAMP}"

if [[ ! -f "$SOURCE_DIR/SKILL.md" ]]; then
  echo "Missing source skill: $SOURCE_DIR/SKILL.md" >&2
  exit 1
fi

install_one() {
  local target_root="$1"
  local target_name="$2"
  local target_dir="$target_root/$SKILL_NAME"
  mkdir -p "$target_root"

  # Older installers kept backups beside live skills, which made Codex and
  # Claude discover several copies of the same skill. Preserve those backups
  # outside the discovery root before installing the authoritative copy.
  local legacy_backups=("$target_root/$SKILL_NAME.bak."*)
  if [[ -e "${legacy_backups[0]}" ]]; then
    mkdir -p "$BACKUP_ROOT/$target_name/legacy"
    local legacy
    for legacy in "${legacy_backups[@]}"; do
      mv "$legacy" "$BACKUP_ROOT/$target_name/legacy/"
      echo "Moved legacy backup $legacy -> $BACKUP_ROOT/$target_name/legacy/"
    done
  fi

  if [[ -e "$target_dir" ]]; then
    mkdir -p "$BACKUP_ROOT/$target_name"
    local backup="$BACKUP_ROOT/$target_name/$SKILL_NAME"
    mv "$target_dir" "$backup"
    echo "Backed up existing $target_dir -> $backup"
  fi

  cp -R "$SOURCE_DIR" "$target_dir"
  echo "Installed $SKILL_NAME -> $target_dir"
}

install_one "$ROOT_DIR/.agents/skills" "codex"
install_one "$ROOT_DIR/.claude/skills" "claude"

echo "Done. Run: $KIT_DIR/verify-install.sh"
