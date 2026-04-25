#!/usr/bin/env bash
# Stop hook: 現在の作業ブランチに紐づく PR の CI 状態を表示する。
# PR が無い場合や main ブランチでは静かに終了する。
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

case "$branch" in
  ""|main|HEAD) exit 0 ;;
esac

if ! command -v gh >/dev/null 2>&1; then
  exit 0
fi

result=$(gh pr checks 2>&1)

if echo "$result" | grep -qiE "no (pull requests|checks reported|open pull request)"; then
  exit 0
fi

echo "──────── CI status (branch: $branch) ────────"
echo "$result" | head -20
echo "─────────────────────────────────────────────"
