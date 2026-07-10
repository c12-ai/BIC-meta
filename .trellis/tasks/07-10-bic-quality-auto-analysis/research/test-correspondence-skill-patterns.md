# Test Correspondence Skill Patterns

## Sources reviewed

- GitHub Quality Playbook:
  https://github.com/github/awesome-copilot/blob/main/skills/quality-playbook/SKILL.md
- OpenAI Playwright Interactive Skill:
  https://github.com/openai/skills/blob/main/skills/.curated/playwright-interactive/SKILL.md
- Superpowers Test-Driven Development Skill:
  https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md
- GSD retroactive validation workflow:
  https://github.com/gsd-build/get-shit-done/blob/main/docs/USER-GUIDE.md

## Reused patterns

Quality Playbook separates a mapped test from a missing test and traces tests to
use cases. BIC reuses that distinction as changed behavior mapped to an existing
test versus no mapped test. It does not reuse test execution, generated tests,
confidence, or ship/block gates.

Playwright Interactive builds one QA inventory from requested requirements,
implemented behavior, and final claims, then requires every item to map to a
check and adds off-happy-path scenarios. BIC reuses the behavior-to-check
inventory and error/edge-scenario prompts, but performs static inspection only.

Superpowers requires tests for new functions plus edge and error behavior and
warns against tests that only verify mocks. BIC reuses these as missing-test
heuristics, not as TDD execution rules.

GSD retroactive validation maps requirements to tests, analyzes gaps, and
separates automated from manual-only verification. BIC reuses the mapping and
gap shape while leaving execution and test generation outside this Skill.

## BIC-specific decision

Keep relation and action separate:

1. Relation facts: direct, safe indirect/explicit, or possible.
2. Add-test guidance: add a test, strengthen a test, or no obvious static gap.

Do not replace either dimension with a single high/medium/low score. Preserve
`(repo, module_scope)` on every relation and require explicit repository targets
for cross-repository semantic mappings.
