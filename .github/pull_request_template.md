## What

Briefly describe the change. One or two sentences.

## Why

Why does this change exist. Link the related issue.

Closes #

## How

How was the change implemented. Call out anything non obvious.

## Test plan

- [ ] Local checks pass: `pnpm lint && pnpm typecheck && pnpm test`
- [ ] Pre commit hooks pass: `pre-commit run --all-files`
- [ ] For IaC changes: `tofu fmt -recursive` and `tofu validate` in the affected `infra/live/<env>` directory
- [ ] For engineering calculation or prompt changes: the relevant eval suite ran green and the delta was reviewed

## Reviewer checklist

- [ ] One reviewer approval, two for changes that touch agents, prompts, evals, code modules, citations, or anything that could change a stampable deliverable
- [ ] All CI checks green
- [ ] If a long lived choice was made, an ADR is added in `docs/decisions/`
- [ ] If user facing strings changed, both German and English locales updated
- [ ] No private docs staged (`git status` shows no internal-only file)
- [ ] No em dashes, en dashes, or double hyphens in prose (enforced by CI, double check on review)
- [ ] No AI co author trailer in commit messages or PR body

## Notes

Anything else the reviewer should know.
