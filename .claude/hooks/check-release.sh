#!/usr/bin/env bash
# Stop hook: main で release-worthy な未リリース commit があれば Claude に通知し、
# 自動 release を促す。feedback_release_check_per_pr.md のルール準拠。
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
[ "$branch" = "main" ] || exit 0

last_tag=$(git describe --tags --abbrev=0 2>/dev/null) || exit 0
[ -n "$last_tag" ] || exit 0

# release-worthy: feat:/fix: prefix (with optional scope and !) or BREAKING CHANGE in body
worthy=$(git log "${last_tag}..HEAD" -E \
  --grep='^(feat|fix)(\(.+\))?!?:' \
  --grep='BREAKING CHANGE' \
  --format='%h %s' 2>/dev/null)
[ -n "$worthy" ] || exit 0

{
  echo "──── release check (main, since $last_tag) ────"
  echo "$worthy" | head -20
  echo
  echo "feedback_release_check_per_pr.md に従って release を切ってください"
  echo "（breaking/feat → minor bump, fix only → patch bump, docs/chore/refactor のみなら release 不要）"
  echo "─────────────────────────────────────────────"
} >&2
exit 2
