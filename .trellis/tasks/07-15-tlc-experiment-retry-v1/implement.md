# Implementation Plan — TLC user-initiated experiment retry V1

1. Agent Service — completed
   - Added the pure TLC fresh-retry draft helper and optional retry event fields.
   - Made TLC result-review reject cleanup the old aggregator, then atomically
     persist decision confirmation plus the new trial; the worker only narrates.
   - Added the terminal-failure retry Facade/route and deterministic idempotency.
   - Fixed synchronous dispatch failure to persist the execution axis and error.
2. Portal — completed
   - Added the retry client call, localized TLC-only labels, and failure CTA.
   - Added the retry event handoff that selects the new attempt and opens the
     existing Material Preparation dialog with the clean draft.
3. Verify — completed
   - Agent focused tests, real PostgreSQL route integration, Ruff, and Pyright pass.
   - Portal focused/regression tests, typecheck, i18n, build, and diff checks pass.
   - Independent Trellis re-check found no remaining blocker.
4. Reconcile — completed
   - Updated root PRD and affected Agent/Portal contract specs.
   - Final handoff reports every modified document/code/test file by repository.
