#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$KIT_DIR/../.." && pwd)"
SKILL_NAME="bic-quality-guan-ping-ce"
SOURCE_DIR="$KIT_DIR/skill/$SKILL_NAME"

check_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Missing file: $path" >&2
    exit 1
  fi
}

check_dir() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    echo "Missing directory: $path" >&2
    exit 1
  fi
}

check_workspace_root() {
  local script="$1"
  local tmp
  tmp="$(mktemp)"
  bash "$script" > "$tmp"
  python3 -c 'import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
expected = sys.argv[2]
root = data.get("workspace_root") or data.get("context", {}).get("workspace_root")
if root != expected:
    raise SystemExit(f"{sys.argv[3]} reported workspace_root={root!r}, expected {expected!r}")
' "$tmp" "$ROOT_DIR" "$script"
  rm -f "$tmp"
}

compare_skill_copy() {
  local target="$1"
  if ! diff -qr -x "__pycache__" -x "*.pyc" -x "*.pyo" "$SOURCE_DIR" "$target" >/dev/null; then
    echo "Installed skill differs from source: $target" >&2
    diff -qr -x "__pycache__" -x "*.pyc" -x "*.pyo" "$SOURCE_DIR" "$target" >&2 || true
    exit 1
  fi
}

check_dir "$SOURCE_DIR"
check_file "$SOURCE_DIR/SKILL.md"
check_dir "$SOURCE_DIR/agents"
check_file "$SOURCE_DIR/agents/openai.yaml"
check_file "$SOURCE_DIR/config/scope-taxonomy.yaml"
check_file "$SOURCE_DIR/config/test-inventory.yaml"
check_file "$SOURCE_DIR/config/risk-model.yaml"
check_file "$SOURCE_DIR/references/risk-model.md"
check_file "$SOURCE_DIR/references/test-analysis-rules.md"
check_file "$SOURCE_DIR/scripts/quality_context.py"
check_file "$SOURCE_DIR/scripts/issue_context.py"
check_file "$SOURCE_DIR/scripts/risk_assessment.py"
check_file "$SOURCE_DIR/scripts/symbol_extraction.py"
check_file "$SOURCE_DIR/scripts/test_assets.py"
check_file "$SOURCE_DIR/scripts/test_relations.py"
check_file "$SOURCE_DIR/scripts/collect-quality-context.sh"
check_file "$SOURCE_DIR/scripts/detect-impact-scope.sh"
check_file "$SOURCE_DIR/scripts/inspect-test-inventory.sh"
check_file "$SOURCE_DIR/scripts/suggest-test-scope.sh"
check_file "$SOURCE_DIR/scripts/assess-risk-matrix.sh"

python3 -m json.tool "$SOURCE_DIR/config/scope-taxonomy.yaml" >/dev/null
python3 -m json.tool "$SOURCE_DIR/config/test-inventory.yaml" >/dev/null
python3 -m json.tool "$SOURCE_DIR/config/risk-model.yaml" >/dev/null
python3 -m unittest discover -s "$KIT_DIR/tests" -v

check_workspace_root "$SOURCE_DIR/scripts/collect-quality-context.sh"
check_workspace_root "$SOURCE_DIR/scripts/detect-impact-scope.sh"
bash "$SOURCE_DIR/scripts/inspect-test-inventory.sh" >/dev/null
check_workspace_root "$SOURCE_DIR/scripts/suggest-test-scope.sh"
check_workspace_root "$SOURCE_DIR/scripts/assess-risk-matrix.sh"

if [[ -d "$ROOT_DIR/.agents/skills/$SKILL_NAME" ]]; then
  echo "Codex project skill installed: $ROOT_DIR/.agents/skills/$SKILL_NAME"
  compare_skill_copy "$ROOT_DIR/.agents/skills/$SKILL_NAME"
  check_file "$ROOT_DIR/.agents/skills/$SKILL_NAME/agents/openai.yaml"
  check_workspace_root "$ROOT_DIR/.agents/skills/$SKILL_NAME/scripts/suggest-test-scope.sh"
else
  echo "Codex project skill not installed yet. Run install.sh if desired."
fi

if [[ -d "$ROOT_DIR/.claude/skills/$SKILL_NAME" ]]; then
  echo "Claude project skill installed: $ROOT_DIR/.claude/skills/$SKILL_NAME"
  compare_skill_copy "$ROOT_DIR/.claude/skills/$SKILL_NAME"
  check_file "$ROOT_DIR/.claude/skills/$SKILL_NAME/agents/openai.yaml"
  check_workspace_root "$ROOT_DIR/.claude/skills/$SKILL_NAME/scripts/suggest-test-scope.sh"
else
  echo "Claude project skill not installed yet. Run install.sh if desired."
fi

echo "BIC quality kit verification passed."
