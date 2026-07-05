# Check Results

## 2026-07-05

Commands run from `BIC-agent-portal`:

```bash
./node_modules/.bin/biome check src/components/workspace/material-preparation/MaterialPreparationPanel.tsx src/components/workspace/forms/TubeSelectorGrid.tsx tests/fixtures/workspace-state-gating.tsx tests/material-preparation-layout.spec.ts docs/project-prd.md
./node_modules/.bin/tsc -b --noEmit
./node_modules/.bin/vitest run src/components/workspace/forms/TubeSelectorGrid.test.ts
./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts --project=chromium -g "TLC material preparation"
```

Result: all passed.

Follow-up after reviewing Feishu interaction documents:

- Source read:
  - `https://carbon12.feishu.cn/wiki/KS6kw4WLPiyIYbkn1f3c98SSn3b` (`交互文档-物料准备和耗材维护`)
  - embedded wiki doc `AKmcweV5iiorPWkQTY1cBdWOnxc` (`实验室信息维护配置表`)
- Saved Markdown copies:
  - `/Users/drakezhou/Downloads/交互文档-物料准备和耗材维护.md`
  - `/Users/drakezhou/Downloads/实验室信息维护配置表.md`
- Missing PRD content added:
  - two Material Preparation entry paths: Parameter Design and dispatch readiness failure;
  - page layout: return-to-parameters action, task/objective header, rack filter, maintenance entry, left material card/list, right physical layout;
  - task cards split manual/specific items from robot auto-pick items;
  - manual assign/view/update/highlight/hover-metadata expectations;
  - robot auto-pick stock ratio, confirm-all, zero-stock disabled state;
  - lab material configuration source as authority for rack/material/task requirement classification;
  - unresolved conflicts from the external docs: TLC `1 or 2`/demo-one-location vs current `2-4` dispatch contract, and empty-slot assignment vs current maintained-item selection semantics.

Validation:

```bash
git diff --check -- Production-PRD.md .trellis/tasks/07-05-lab-logistics-maintenance/prd.md
git diff --check -- docs/project-prd.md
python3 .trellis/scripts/task.py validate .trellis/tasks/07-05-lab-logistics-maintenance
```

Result: all passed.

Follow-up after Drake flagged that the right-side Maintenance module was still inconsistent between CC and TLC:

- Root cause: the first refactor only reused the outer `SpecialItemPreparationModule` (readiness list, right-panel header, toggle, body switch). The actual right-side maintenance body still diverged: CC rendered `RackPlaneView`, while TLC rendered a separate `SampleTubeMaintenanceGrid`. That meant the visible Maintenance module was not truly shared.
- Fix: removed the TLC-only `SampleTubeMaintenanceGrid` and changed CC maintenance mode to stop rendering `RackPlaneView`. Both CC and TLC now adapt their data into maintenance groups/cells and render the same `SpecialItemMaintenanceGrid`.
- Structural check: `rg "SampleTubeMaintenanceGrid|renderMaintenanceBody=\\{\\(\\) => \\(<RackPlaneView"` returns no matches in `MaterialPreparationPanel.tsx`.
- Regression: focused Playwright now asserts both CC and TLC maintenance mode show `data-testid="special-item-maintenance-grid"`.

Commands run from `BIC-agent-portal`:

```bash
./node_modules/.bin/biome check src/components/workspace/material-preparation/MaterialPreparationPanel.tsx src/components/workspace/forms/TubeSelectorGrid.tsx tests/material-preparation-layout.spec.ts
./node_modules/.bin/tsc -b --noEmit
./node_modules/.bin/vitest run src/components/workspace/forms/TubeSelectorGrid.test.ts
./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts --project=chromium -g "TLC material preparation|material preparation separates"
```

Result: all passed.

Additional observation: running the full `tests/material-preparation-layout.spec.ts` currently fails on two pre-existing CC assertions unrelated to this TLC change:

- floor selector expects `[data-rack-floor="L4"]` for Sample Cartridge;
- CC params editing test cannot find `/Slot 006.*bic_09B_l4_006/`.

Follow-up after shared component refactor:

```bash
./node_modules/.bin/biome check src/components/workspace/material-preparation/MaterialPreparationPanel.tsx src/components/workspace/forms/TubeSelectorGrid.tsx tests/fixtures/workspace-state-gating.tsx tests/material-preparation-layout.spec.ts docs/project-prd.md
./node_modules/.bin/tsc -b --noEmit
./node_modules/.bin/vitest run src/components/workspace/forms/TubeSelectorGrid.test.ts
./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts --project=chromium -g "TLC material preparation|material preparation separates"
```

Result: all passed after correcting the CC fixture floor for sample-cartridge slots to L4.

Final follow-up after updating `BIC-agent-portal/.trellis/spec/ui/L3/form.md`:

```bash
rg "declaredTubeId|Model B|empty cells are selectable|mints a deterministic|chemist DECLARES|Declare 2" BIC-agent-portal/.trellis/spec/ui/L3/form.md BIC-agent-portal/docs/project-prd.md BIC-agent-portal/src/components/workspace/material-preparation BIC-agent-portal/src/components/workspace/forms/TubeSelectorGrid.tsx -n
./node_modules/.bin/biome check src/components/workspace/material-preparation/MaterialPreparationPanel.tsx src/components/workspace/forms/TubeSelectorGrid.tsx tests/fixtures/workspace-state-gating.tsx tests/material-preparation-layout.spec.ts docs/project-prd.md
./node_modules/.bin/tsc -b --noEmit
./node_modules/.bin/vitest run src/components/workspace/forms/TubeSelectorGrid.test.ts
./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts --project=chromium -g "TLC material preparation|material preparation separates"
```

Result: no stale empty-cell declaration references found; all focused checks passed.

Final correction after narrowing special-item maintenance scope and fixing TLC sample-tube selection:

```bash
rg "source=storage|storage-source|rack-level sample-tube|backend contract gap|no cell-level endpoint|filterRacksByMaterialKeys|TlcWorkspaceView|TLC Workspace|workspace slot mutation|updatePreparationSlot for TLC" BIC-agent-portal/docs/project-prd.md BIC-agent-portal/.trellis/spec/ui/L3/form.md .trellis/tasks/07-05-lab-logistics-maintenance BIC-agent-portal/src/components/workspace/material-preparation/MaterialPreparationPanel.tsx BIC-agent-portal/tests/material-preparation-layout.spec.ts -n
```

Result: no stale storage/TLC-workspace/slot-maintenance references found.

Commands run from `BIC-agent-portal`:

```bash
./node_modules/.bin/biome check src/components/workspace/material-preparation/MaterialPreparationPanel.tsx src/components/workspace/forms/TubeSelectorGrid.tsx src/lib/lab-service-client.ts src/lib/lab-service-queries.ts tests/fixtures/workspace-state-gating.tsx tests/material-preparation-layout.spec.ts docs/project-prd.md .trellis/spec/ui/L3/form.md
./node_modules/.bin/tsc -b --noEmit
./node_modules/.bin/vitest run src/components/workspace/forms/TubeSelectorGrid.test.ts
./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts --project=chromium -g "TLC material preparation|material preparation separates"
```

Result: all passed. The focused Playwright coverage verifies that TLC maintenance uses the dispatchable bench sample-tube cell endpoint, TLC maintenance exposes no silica/tank/tip/generic consumables, TLC selection uses filled bench tubes, and CC maintenance remains scoped to sample-cartridge slots.

After renaming the remaining test/comment wording from workspace maintenance to sample-tube maintenance, the same portal focused command chain was rerun and passed again.

Follow-up after Drake reported that selected TLC tubes still left Validate Readiness disabled:

- Root cause: the portal already enforced the robot dispatch shape (`2-4` tubes, one box, one row, contiguous columns starting at column 1), but the disabled button only showed a generic "Select 2-4 existing sample tubes" footer message. If the chemist selected filled tubes such as `A2+A3`, the real blocker was "Sample tubes must start at column 1", but the UI did not say that.
- Fix: `MaterialPreparationPanel` now derives a `readinessBlocker` string from the same gate that disables the button and renders it in `data-testid="material-readiness-status"` plus the button title.
- Regression: added a Playwright case where `A2+A3` are selected and the button remains disabled with `Sample tubes must start at column 1.`

Commands run from `BIC-agent-portal`:

```bash
./node_modules/.bin/biome check src/components/workspace/material-preparation/MaterialPreparationPanel.tsx src/components/workspace/forms/TubeSelectorGrid.tsx tests/material-preparation-layout.spec.ts
./node_modules/.bin/tsc -b --noEmit
./node_modules/.bin/vitest run src/components/workspace/forms/TubeSelectorGrid.test.ts
./node_modules/.bin/playwright test tests/material-preparation-layout.spec.ts --project=chromium -g "TLC material preparation|material preparation separates"
```

Result: all passed.

Commands run from `BIC-lab-service`:

```bash
uv run ruff check app
uv run ruff format --check app
uv run pyright app
uv run pytest tests/e2e/test_sample_tube_boxes_bench.py
```

Result: all passed. Pytest emitted one existing deprecation warning from `command_validator.py` importing `bic_shared_types.robot_protocol`.
