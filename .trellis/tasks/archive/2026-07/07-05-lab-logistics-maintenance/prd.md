# Fix TLC and CC lab logistics maintenance

## Goal

Align the portal Lab Logistics module with the current product rule for experiment-specific
materials:

- Generic consumables remain maintained from the Consumables page.
- Experiment-specific lab items are handled from Parameter Design through the Lab Logistics module.
- This task only covers TLC and CC. RE and FP are out of scope until their lab execution parameters are finalized.

The chemist must be able to use one Lab Logistics module to both maintain the relevant lab item slots and select the concrete items for the current TLC or CC execution.

## Confirmed Facts

- Root `Production-PRD.md` already defines generic consumables, experiment-specific lab items, and the special item module responsibilities.
- Portal has no existing `BIC-agent-portal/docs/project-prd.md`; this task must create the child Project PRD for portal-owned Lab Logistics behavior.
- `MaterialPreparationPanel` already gates parameter dispatch through a Lab Logistics dialog for `tlc`, `cc`, and `re`, but the current scope must effectively support TLC and CC only.
- CC already uses rack layout slots and a maintenance toggle in the Lab Logistics dialog.
- TLC currently uses `GET /preparations/sample-tube-boxes?source=bench` and only renders a sample-tube selector. It does not expose persistent sample-tube cell maintenance inside the Lab Logistics dialog.
- Lab Service already exposes `GET /preparations/sample-tube-boxes?source=bench` for dispatchable TLC sample-tube boxes, but needs a cell-level maintenance endpoint so the special-item module can persistently insert/remove sample tubes in those dispatchable cells.
- The current TLC selector allows choosing empty cells and minting declared tube ids. That behavior conflates experiment selection with maintenance; the new portal behavior should make empty cells maintainable only in maintenance mode and selectable only when the item is present.

## Requirements

- R1. Persist portal-owned Lab Logistics requirements in `BIC-agent-portal/docs/project-prd.md`, linked to `../../Production-PRD.md`.
- R2. The portal Project PRD must state that the current Lab Logistics module scope is TLC and CC only; RE/FP are explicitly out of scope until their lab execution parameters are clarified.
- R3. The CC Lab Logistics dialog must continue to allow the chemist to maintain sample-column slots and select the current execution's sample column.
- R4. The TLC Lab Logistics dialog must provide a maintenance-mode button in the module header/upper-right area, following the Consumables page interaction model.
- R5. In TLC maintenance mode, clicking an eligible dispatchable bench sample-tube cell must persistently add/remove the corresponding sample tube through the Lab Service cell maintenance endpoint.
- R6. In TLC selection mode, the chemist must select only existing sample tubes for the current TLC execution; empty tube cells must not create experiment objects by selection alone.
- R7. TLC selection must still enforce the current dispatch contract: 2-4 sample tubes, one dispatchable bench 2 mL box, one row, contiguous columns starting at column 1.
- R8. The TLC Lab Logistics dialog must preserve readiness validation and dispatch confirmation behavior after maintenance changes by invalidating stale readiness snapshots and refreshing preparation caches.
- R9. Do not add backward-compatibility scaffolding for old TLC empty-cell declaration behavior.
- R10. Special-item Lab Logistics pages must share a single reusable component for module chrome, maintenance-mode toggling, slot maintenance actions, readiness-list layout, and selection/maintenance body switching. TLC and CC may provide experiment-specific render bodies, but must not duplicate the maintenance orchestration logic.
- R11. Special-item Lab Logistics maintenance mode must be scoped to the current experiment's special items only. It must not become a generic consumables/all-items maintenance page.
- R12. In the current TLC/CC scope, the special-item maintenance sets are:
  - TLC: sample tubes only.
  - CC: sample column/sample cartridge only.
- R13. TLC must provide a usable path to select sample tubes in the Lab Logistics module. If no maintained sample tubes are visible/selectable, the module is incomplete.
- R14. Lab Logistics / Material Preparation must be reachable from both Parameter Design and the dispatch readiness validation flow when material state is incomplete or invalid.
- R15. The Material Preparation surface must preserve the interaction-document layout contract: return-to-parameters action, task/objective header, rack filter, maintenance entry, left material card/list, and right physical rack/item layout.
- R16. Task material cards must separate manual/specific items from robot auto-pick items.
- R17. Manual/specific item cards must support assign, view, and update interactions tied to right-side physical area/slot highlighting.
- R18. Assigned slots should expose hover traceability metadata: experiment objective/task identifier and update time; updated-by is out of scope until source data exists.
- R19. Robot auto-pick items must show available stock against capacity, support "confirm all auto-pick", and disable that confirmation when any required auto-pick item has zero available stock.
- R20. Lab material surfaces and task material requirements must be driven by a reviewed configuration source that classifies materials as `有特殊性` or `无特殊性`.
- R21. Known product conflict must remain explicit until resolved: the external interaction/config documents describe TLC sample-tube assignment as `1 or 2` slots and possibly one demo location, while current Lab Logistics enforces the dispatch contract of `2-4` existing tubes in one contiguous dispatchable bench row.
- R22. Known product conflict must remain explicit until resolved: the external interaction document says manual assignment clicks empty slots, while current TLC/CC selection mode selects existing maintained special items and reserves empty-slot clicks for maintenance.

## Acceptance Criteria

- [ ] `BIC-agent-portal/docs/project-prd.md` exists and contains the TLC/CC Lab Logistics behavior contract, inputs/outputs, state flow, edge cases, acceptance criteria, and change log.
- [ ] CC Lab Logistics behavior remains covered by existing tests or an updated focused test.
- [ ] TLC Lab Logistics renders a maintenance toggle and exposes dispatchable bench sample-tube cells in the dialog.
- [ ] TLC maintenance mode exposes only sample-tube maintenance, not TLC silica/tank/tip or generic consumables.
- [ ] A TLC sample-tube cell click in maintenance mode calls `PUT /preparations/sample-tube-boxes/{box_id}/cells/{row}/{col}` with the expected occupied payload and refreshes the visible bench sample-tube state.
- [ ] In TLC selection mode, filled sample-tube cells are selectable and empty sample-tube cells are not selectable.
- [ ] TLC selection mode can select maintained sample tubes from the visible sample-tube surface.
- [ ] CC maintenance mode exposes only sample-column/sample-cartridge maintenance, not all rack consumables.
- [ ] TLC readiness cannot be validated until 2-4 valid existing sample tubes are selected.
- [ ] RE/FP behavior is not expanded in this task.
- [ ] TLC and CC special-item Lab Logistics are routed through the shared special-item module component instead of maintaining separate page-specific wrappers.
- [ ] TLC and CC maintenance mode use the same right-side maintenance grid component; only data adapters differ.
- [ ] PRD captures the two Material Preparation entry paths: Parameter Design and dispatch readiness failure/incomplete-material flow.
- [ ] PRD captures task material cards split into manual/specific items and robot auto-pick items.
- [ ] PRD captures robot auto-pick confirmation, stock ratio display, and zero-stock disabled state.
- [ ] PRD captures manual assignment view/update/highlight/hover-metadata expectations.
- [ ] PRD captures rack filtering as a required header control.
- [ ] PRD captures lab material configuration as the authority for rack areas, material type, slot counts, and task material requirements.
- [ ] PRD records the two unresolved conflicts from the Feishu interaction/config documents without silently changing current TLC dispatch semantics.
- [ ] Verification includes focused frontend tests and type/lint gates appropriate for the touched portal files.

## Notes

- This task intentionally avoids database schema changes. It may add a narrow Lab Service REST endpoint for dispatchable bench sample-tube cell maintenance because existing storage-rack maintenance cannot produce TLC-dispatchable sample-tube selections.
- Feishu sources reviewed on 2026-07-05:
  - `交互文档-物料准备和耗材维护`.
  - `实验室信息维护配置表`.
