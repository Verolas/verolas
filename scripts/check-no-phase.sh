#!/usr/bin/env bash
# Fails the build if user-visible content mentions the word "phase" followed
# by a number, or any internal build step numbering. Files that intentionally
# discuss the rule itself (this script, ADRs documenting the rule, contributing
# guidelines describing the rule) are allowlisted.
#
# Run locally:
#   bash scripts/check-no-phase.sh

set -euo pipefail

# Allowlist of files that legitimately discuss the rule.
allowlist=(
  'scripts/check-no-phase.sh'
  'CONTRIBUTING.md'
  '.github/workflows/pr-meta.yml'
  '.github/workflows/ci.yml'
  'docs/decisions/003-ci-cd-foundation.md'
)

files=()
while IFS= read -r f; do
  files+=("$f")
done < <(git ls-files \
  '*.md' '*.tf' '*.yaml' '*.yml' '*.ts' '*.tsx' '*.js' '*.py' '*.rs' \
  ':!:pnpm-lock.yaml' \
  ':!:.terraform.lock.hcl' \
  ':!:infra/live/*/.terraform.lock.hcl')

violations=0
> /tmp/phase-hits.log

for f in "${files[@]}"; do
  [ -f "$f" ] || continue

  skip=0
  for allowed in "${allowlist[@]}"; do
    if [ "$f" = "$allowed" ]; then
      skip=1
      break
    fi
  done
  [ "$skip" -eq 1 ] && continue

  # Match: "Phase 0", "phase 12", "Phase  3:" but not "phaseTwo" or "phased"
  grep -InE '\bphase[[:space:]]+[0-9]+\b' "$f" >> /tmp/phase-hits.log 2>/dev/null || true
done

if [ -s /tmp/phase-hits.log ]; then
  echo "Forbidden: numbered build step or 'phase N' reference in user-facing content:"
  cat /tmp/phase-hits.log
  rm -f /tmp/phase-hits.log
  exit 1
fi

rm -f /tmp/phase-hits.log
echo "OK: no numbered build step references."
