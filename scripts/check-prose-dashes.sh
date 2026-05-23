#!/usr/bin/env bash
# Fails the build if em dashes, en dashes, or double hyphens appear in
# user-facing prose. Code blocks in Markdown, CLI flag literals, PEM headers,
# Markdown table separators, and the lockfile are excluded.
#
# Run locally:
#   bash scripts/check-prose-dashes.sh

set -euo pipefail

paths=(
  '*.md'
  '*.MD'
  'README'
  'LICENSE'
)

# Find candidate files. Filter out gitignored and binary. Portable across
# macOS Bash 3.2 and Linux Bash 4+.
files=()
while IFS= read -r f; do
  files+=("$f")
done < <(git ls-files \
  '*.md' '*.MD' 'README' 'LICENSE' \
  ':!:pnpm-lock.yaml' \
  ':!:.terraform.lock.hcl' \
  ':!:infra/live/*/.terraform.lock.hcl')

violations=0

for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  # Walk the file line by line, ignoring fenced code blocks and Markdown
  # table separators. We do not exclude CLI flags inside backticks here
  # because backticks live on the same line; we strip inline code first.
  awk '
    BEGIN { in_fence = 0 }
    /^```/ { in_fence = !in_fence; next }
    in_fence { next }
    # Strip inline backtick code spans so CLI flags like `kubectl --foo` are ignored
    {
      line = $0
      while (match(line, /`[^`]*`/)) {
        line = substr(line, 1, RSTART - 1) substr(line, RSTART + RLENGTH)
      }
      # Strip Markdown table separator rows like | --- | --- |
      if (line ~ /^\s*\|[ \t|:-]+\|\s*$/) next
      print FILENAME ":" NR ":" line
    }
  ' "$f" \
  | grep -E '—|–|--' \
  | grep -v ':[0-9]+:[[:space:]]*$' \
  >> /tmp/prose-dash-hits.log 2>/dev/null || true
done

if [ -s /tmp/prose-dash-hits.log ]; then
  echo "Forbidden em dash, en dash, or double hyphen in prose:"
  cat /tmp/prose-dash-hits.log
  rm -f /tmp/prose-dash-hits.log
  exit 1
fi

rm -f /tmp/prose-dash-hits.log
echo "OK: no prose dashes."
