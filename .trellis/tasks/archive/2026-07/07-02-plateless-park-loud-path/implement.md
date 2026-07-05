# Implement — plateless-park loud path

Repo: /Users/drakezhou/Development/BIC/BIC-agent-service. Branch: `fix/plateless-park-loud-path`
off main @ 7d2b1ba. DO NOT touch `app/infrastructure/llm_client.py` (dirty, in-flight, not ours).
Read `research/fix-seams.md` + `design.md` first. Match repo conventions (English comments).

## Checklist (ordered)
1. [ ] Write the failing non-mocked regression test first (real FastPathHandlers wiring per
       `test_fast_path_handlers_system.py`); confirm it FAILS on main (silent return).
2. [ ] event_ingress.py plateless branch (warn + delegate to terminal flow) per design §1.
3. [ ] tlc.py `_NARRATE_PROMPT_LAB_TASK_FAILED` + `_build_narrate_prompt` branch per design §2.
4. [ ] Update mocked routing test at test_event_ingress.py:236 (re-pin new routing, honest
       docstring); add narrate-prompt unit test.
5. [ ] Full gate chain, re-run WHOLE chain after any fix (gates short-circuit):
       `uv run pytest tests -x -q` && repo lint/type gates (mirror Makefile/CI: `make lint`
       or `uv run ruff check . && uv run ruff format --check .`; pyright if CI runs it —
       scan app/ only per CI convention).
6. [ ] Verify diff touches ONLY: event_ingress.py, tlc.py, the 3 test files. Nothing else.

## Validation
- New system test red on main → green on branch (prove it: run once with fix stashed if cheap).
- Zero skipped tests in touched files; report full gate output verbatim.
