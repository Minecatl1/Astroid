#!/usr/bin/env bash
set -euo pipefail

# Resolves the known Astroid bot conflict set by preferring this branch's versions.
# Use when GitHub reports conflicts in these files.

FILES=(
  ".gitignore"
  "README.md"
  "src/Bot/.config.py"
  "src/Bot/config.py"
  "src/Bot/nerimity_bot.py"
  "src/Bot/stoat_bridge.py"
)

if ! git rev-parse -q --verify MERGE_HEAD >/dev/null; then
  echo "No merge in progress. Start a merge/rebase first, then run this script."
  exit 1
fi

for file in "${FILES[@]}"; do
  if git ls-files -u -- "$file" | grep -q .; then
    git checkout --ours -- "$file"
    git add "$file"
    echo "Resolved with ours: $file"
  else
    echo "No conflict in: $file"
  fi
done

if git diff --name-only --diff-filter=U | grep -q .; then
  echo "Some conflicts remain in other files. Resolve them manually."
  git diff --name-only --diff-filter=U
  exit 2
fi

echo "Known conflicts resolved. Run tests, then finish merge:"
echo "  git commit"
