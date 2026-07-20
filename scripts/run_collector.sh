#!/usr/bin/env bash
# One collection cycle: scrape -> write data/ -> commit & push only if data changed.
# Called by launchd on a schedule, or run by hand. Safe to run repeatedly.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

[ -f venv/bin/activate ] && source venv/bin/activate

python -m collector.run "$@"

# Commit + push only when the snapshot actually changed (keeps git history quiet
# and only triggers a Pages redeploy on real changes).
if ! git diff --quiet -- data/ 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard data/)" ]; then
  git add data/
  git commit -q -m "data: restock snapshot $(date -u +%FT%TZ)"
  if git push -q origin main 2>/dev/null; then
    echo "pushed data update"
  else
    echo "push failed — check 'git remote -v' and auth (gh auth login)"
  fi
else
  echo "no data change; nothing to push"
fi
