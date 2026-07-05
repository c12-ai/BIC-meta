# BIC Production PRD

## Status

- Owner: Drake
- Review state: Draft
- Last updated: 2026-07-05

## Scope

This Production PRD defines the cross-repo product behavior for the BIC chemistry copilot workflow across:

- `BIC-agent-portal`: the user-facing portal.
- `BIC-agent-service`: the Agent backend and copilot orchestration service.
- `BIC-lab-service`: Nexus / LIMS and robot orchestration service.

Agent-only reasoning behavior and Agent Copilot self-behavior are refined in `BIC-agent-service/docs/project-prd.md`.

## Problem / Goal

Chemists need a copilot-driven system that can turn an experiment objective into an executable lab workflow, collect the required human inputs, coordinate robot/manual execution, and return evidence and results in one traceable product flow.

The system must keep the human in control of ambiguous or authority-sensitive decisions while still automating lab-state queries, workflow planning, robot dispatch, and result collection where the system has enough information and authority.

## Users and Scenarios

Primary user:

- Chemist using the BIC portal to plan, execute, monitor, and review an experiment workflow.

Core scenarios:

1. The chemist enters an experiment objective in the portal.
2. The Agent Service interprets the objective and proposes a workflow.
3. The system collects required parameters through dedicated forms.
4. The chemist reviews and confirms workflow and execution parameters.
5. The Agent Service dispatches robot-capable steps to Nexus / Lab Service.
6. Manual steps are completed by the chemist and reported back through the product surface.
7. The portal shows execution progress, evidence, and final results.

## Product Requirements

1. **Objective-first workflow**
   - The product starts from the chemist's experiment objective.
   - The objective drives workflow planning and parameter collection.
   - The portal must keep the active session and workflow context visible to the chemist.

2. **Human-controlled confirmation**
   - The chemist must confirm workflow and execution parameters before the system dispatches execution.
   - The system must not silently execute authority-sensitive actions on behalf of the chemist.

3. **Dedicated form collaboration**
   - The copilot collaborates with the chemist through dedicated forms for the current phase/job.
   - Missing fields must remain explicit rather than being filled with fabricated placeholders.
   - Agent-specific form behavior is refined in the Agent Service Project PRD.

4. **Robot vs manual execution**
   - Each planned step is either robot-executed or manual.
   - Robot steps are dispatched to Lab Service / Nexus and completed through robot result reporting.
   - Manual steps are completed by the chemist and require human-provided completion evidence or result input.

5. **Lab-state backed execution**
   - Lab Service is the product authority for lab state, material/equipment status, and robot orchestration.
   - Agent Service must use Lab Service for lab-side state and dispatch decisions rather than inventing lab state.

6. **Progress and result visibility**
   - The portal must show execution progress across the active workflow.
   - Result evidence should remain visible and traceable after it is produced.
   - The chemist should be able to review final outputs without losing workflow context.

7. **Cross-service consistency**
   - Portal, Agent Service, and Lab Service must agree on workflow/session/task identifiers required to connect planning, execution, and result review.
   - Cross-service product behavior belongs in this Production PRD; repo-owned implementation behavior belongs in child Project PRDs or engineering specs.

8. **AI-engine backed intelligence**
   - ChemEngine (the model service maintained by the Algo Team, "Mind") is the product
     authority for AI-generated experiment intelligence: objective parsing (reaction
     material parse, goal confirmation), parameter recommendation (TLC solvent system,
     CC column choice, RE parameters), and vision-based result analysis (TLC plate
     recognition, CC result analysis).
   - Agent Service must obtain this intelligence from ChemEngine rather than fabricating
     it; when the ChemEngine integration is unavailable or fails, the failure must
     surface to the product flow loudly instead of being silently substituted.
   - Exception: RE realtime result analysis is owned by the Robot Team's Mars system,
     not ChemEngine.
   - Images that ChemEngine must analyze (TLC plate photos, CC result pictures) are
     transferred as presigned URLs from the product's S3-compatible object store.
     Both AWS S3 and MinIO are supported stores; deployments must ensure ChemEngine
     can reach the store network (client deployments co-locate ChemEngine and MinIO
     on the same network).

9. **Material preparation and maintenance separation**
   - Material Preparation is the dispatch-time workflow for experiment-specific items that require human assignment or identity tracking.
   - Consumable Maintenance is the inventory upkeep workflow for non-specific items that the robot can auto-pick.
   - The product must not let a Material Preparation surface become a generic consumables editor, and must not let Consumable Maintenance assign experiment-specific items for a task.
   - A robot dispatch attempt must validate the current task's material state. If validation fails, the user must be guided back to Material Preparation to complete missing or invalid assignments before dispatch.

## Core Concepts

1. **Experiment Objective**
   - The user's high-level experimental intent.
   - The objective is the first user-confirmed product artifact.
   - Workflow planning must be derived from the confirmed objective, not from an unconfirmed draft.

2. **Workflow Design / Plan**
   - The planned experiment workflow generated from the confirmed Experiment Objective.
   - The plan defines which experiment stages are included and whether each stage is robot-executed or manual.
   - The plan must be confirmed by the user before the system generates executable experiment parameters.

3. **Parameter Design**
   - The stage-specific parameter design generated after plan confirmation.
   - Parameter Design applies only to experiment stages that require system-generated execution parameters.
   - Supported experiment types include TLC, CC, RE, and FP:
     - TLC: thin layer chromatography.
     - CC: column chromatography.
     - RE: rotary evaporation.
     - FP: fraction collection / fraction preparation.

## Business Logic

The production workflow is organized around a chemistry purification flow that can include:

- TLC: thin layer chromatography.
- CC: column chromatography.
- FP: fraction preparation / collection.
- RE: rotary evaporation.

The workflow may contain both robot and manual steps. The type of a step determines who executes it and who reports completion:

- **Robot step**: the system dispatches the step to Lab Service / Nexus; the robot executes it; Lab Service reports progress and result updates.
- **Manual step**: the chemist performs the work at the bench; the chemist reports completion and provides required evidence through the product surface.

TLC evidence flows into downstream recommendation and review. When TLC was robot-executed, downstream stages should consume robot-produced evidence. When TLC was manual, the chemist must provide the relevant TLC evidence at the appropriate downstream review point.

## Experimental Execution Flow: TLC Example

1. **Pre-confirmation**
   - The user must first confirm the Experiment Objective.
   - After objective confirmation, the user must confirm the Workflow Design / Plan.
   - Experiment parameter generation must not begin before both confirmations are complete.

2. **Plan scope controls Parameter Design**
   - The Plan page defines which stages are included and which stages are robot-executed or manual.
   - Example: if the user selects TLC and CC as robot-executed stages and selects RE as manual, the Parameter Design section contains only TLC and CC parameters.
   - Manual stages are still part of the business workflow, but they do not require robot-execution parameter generation in the Parameter Design section.

3. **TLC parameter design and generation**
   - After the plan is confirmed, the system automatically helps generate and fill TLC parameters.
   - The generated TLC parameters must remain reviewable by the user.
   - The user must confirm the TLC parameters before the flow can proceed to lab logistics confirmation.

4. **Lab Logistic confirmation**
   - After TLC parameters are confirmed, the user must confirm the Lab Logistic parameters for the TLC execution.
   - Lab Logistic confirmation connects the user-approved experiment design to concrete lab-side item/location usage.
   - The system must not dispatch the TLC experiment before the required Lab Logistic parameters are confirmed.

## Experiment Item Management Rules

1. **Generic consumables**
   - Items without experiment-specific identity can be configured and maintained in the Consumable Maintenance page.
   - The entry point is the button in the upper-right corner of the Consumable Maintenance page.
   - Clicking the button enters maintenance mode.
   - In maintenance mode, clicking a concrete slot icon means adding the corresponding item to that slot.
   - Adding or removing items is persisted to the database when the user exits maintenance/edit mode.
   - Consumable Maintenance is the appropriate place for generic stock/configuration upkeep that is not tied to one experiment's dispatch-time design.

2. **Experiment-specific lab items**
   - Items with experiment-specific identity or placement requirements must be maintained manually by the user during the experiment design/dispatch flow.
   - Examples include sample tubes for TLC and sample columns for CC.
   - The entry point is in the Parameter Design stage for the current experiment.
   - Different experiment types, such as TLC, CC, and RE, can open this maintenance module from their own experiment design context.
   - The maintainable item range is shared across experiment types, while the selected items differ by the current experiment's needs.
   - The module has an upper-right button, following the Consumable Maintenance page pattern, that lets the user enter maintenance mode.
   - In maintenance mode, the user can insert an item into the corresponding item slot.
   - Exiting maintenance/edit mode persists the user's item additions/removals to the database.
   - These experiment-specific items should not be configured as generic reusable consumables outside the experiment context.

3. **Special item module responsibilities**
   - The module maintains lab inventory that contains experiment-specific items.
   - The module also lets the user select which maintained items are used by the current experiment.
   - For TLC, the user must select the sample tubes used by the current experiment.
   - For CC, the user must select the sample column used by the current experiment.

4. **Material Preparation page responsibilities**
   - The Material Preparation surface contains task-level material cards.
   - Each task card separates:
     - manual/specific items, whose exact item or slot must be assigned by the chemist; and
     - robot auto-pick items, whose matching prepared stock must be present and confirmed.
   - Manual/specific item assignment must provide assign, view, and update flows so the chemist can record or change the exact physical item/location used by the task.
   - Robot auto-pick items must show available stock against capacity, such as `3/6`.
   - The product must block the "confirm all auto-pick" action when any required auto-pick item has zero available stock.
   - Confirming auto-pick items records that the user accepted the current non-specific stock state for dispatch readiness.

5. **Lab material configuration source**
   - Lab rack layout, material type (`有特殊性` / `无特殊性`), material areas, slot counts, and task material requirements must be driven by a reviewed lab material configuration source.
   - Material classification has exactly two tiers: specific (`有特殊性`) and non-specific (`无特殊性`). "Unique" is the retired earlier name for specific; no third tier exists.
   - The configuration source must identify which materials are experiment-specific and which are generic/non-specific.
   - The configuration source must also identify which task requires each material and whether that material is manual/specific or robot auto-pick.
   - The configuration source covers the chemist-facing shelf regions (see rule 7). Robot-internal
     parking slots (the robot bench the carry ops target) are owned by the robot protocol and lab
     execution state, and are deliberately excluded from the chemist-facing configuration source.

6. **TLC physical inventory integrity**
   - Lab Service is the authority for TLC physical inventory and must persist a meaningful physical
     layout for every TLC inventory item.
   - A TLC inventory record is valid only when it has at least one of:
     - a concrete `location_id`, meaning the object is located at a specific lab slot; or
     - a `parent_object_id`, meaning the object is contained inside another physical object, such as
       a sample tube inside a tube box.
   - A TLC inventory record with both `location_id` and `parent_object_id` missing is invalid because
     it does not describe any meaningful lab state.
   - TLC readiness must be based on real physical inventory records and must not be satisfied by
     placeless placeholder rows.
   - There is no TLC "staining jar" concept. TLC uses developing tanks. Product, service, and
     readiness logic must not expose or require a staining-jar item.
   - `eluent_tube_pair_50ml` is not a separate TLC physical inventory object and must not be required
     as a readiness item.
   - Waste-tip bins are real TLC physical objects and must have a concrete persisted location.
   - Tip boxes are real TLC physical inventory. They must exist in the initial or maintained lab
     inventory with concrete locations before execution. Allocation may choose an existing tip-box ID
     for a task, but must not create tip-box inventory rows during allocation.

7. **TLC sample-tube inventory model: shelf is the chemist surface; the robot carries**
   (decided 2026-07-05; revised same day per the robot protocol — supersedes the earlier
   bench-selection wording)
   - The supply-shelf sample-tube boxes (two layers) are the chemist's surface for BOTH
     maintenance and selection: the chemist prepares tubes in a shelf box and selects that box's
     tubes for the experiment.
   - At execution start (first round only) the robot itself carries the required boxes from the
     supply shelf to its bench: the selected 2ml sample box, the 50ml solvent box, and both tip
     boxes. The bench slots are robot-internal parking, not a chemist surface.
   - The system must resolve the carry coordinates (layer/side/column) from each box's actual
     recorded inventory placement — the chemist's selected box determines where the robot picks.
     Fixed example coordinates from protocol documents must never be dispatched when placement is
     known.
   - The Consumable Maintenance page shows shelf sample-tube stock read-only; specific items are
     never editable there (rule 1 vs rule 2 separation).
   - The product surface must explain that the robot fetches the box from the shelf itself, so
     the chemist never hand-stocks the robot bench.

8. **Assignment semantics: maintain-then-select** (decided 2026-07-05, applies to CC and TLC uniformly)
   - Assigning a manual/specific item to a task means SELECTING an already-maintained physical
     item; selection must never create inventory.
   - Empty slots or cells are filled and cleared only in maintenance mode.
   - This supersedes the external interaction document's description of assignment as clicking an
     empty slot; the Feishu document must be corrected at source.

9. **TLC sample-tube dispatch quantity contract** (confirmed 2026-07-05)
   - A TLC robot dispatch requires 2–4 sample tubes in ONE shelf sample-tube box, one row,
     contiguous columns, starting at column 1 (the shape rule applies within the box the robot
     carries).
   - The external interaction document's `1 or 2` quantity (and one-location demo note) is stale
     and must be corrected at source; no 1-tube dispatch support is planned.

## UI Interaction Requirements

For the TLC Lab Logistic panel:

- The panel should display TLC-specific Lab Logistic parameters after TLC Parameter Design is confirmed.
- The right side of the panel should show empty sample tube positions for the TLC-relevant slots.
- The user must be able to use this panel to confirm the concrete sample tube placement needed for TLC execution.

## Acceptance Criteria

- A chemist can start from an objective and reach a planned workflow without switching products.
- The chemist can review and confirm parameters before execution dispatch.
- Parameter Design begins only after both Experiment Objective and Workflow Design / Plan are confirmed.
- If TLC and CC are robot-executed and RE is manual, Parameter Design includes TLC and CC parameters only.
- TLC Lab Logistic confirmation happens after TLC parameter confirmation and before TLC dispatch.
- Experiment-specific items such as sample columns and sample tubes are configured during experiment design/dispatch, not as generic consumables.
- Generic consumables can be configured through Consumable Maintenance by entering maintenance mode from the upper-right button, clicking slot icons, and exiting edit mode to persist changes.
- The special item maintenance module is available from the Parameter Design stage and can maintain experiment-specific lab items while also selecting the items required by the current experiment.
- Exiting special item maintenance/edit mode persists item additions/removals to the database.
- Dispatch material validation can route the user back to Material Preparation when task material state is incomplete or invalid.
- Material Preparation task cards separate manual/specific items from robot auto-pick items.
- Robot auto-pick materials show available stock against capacity and cannot be confirmed when required stock is unavailable.
- TLC experiment design lets the user select sample tubes for the current experiment.
- CC experiment design lets the user select the sample column for the current experiment.
- The TLC Lab Logistic panel shows empty sample tube positions for TLC-relevant slots.
- TLC inventory state has no records with both `location_id` and `parent_object_id` missing.
- The Material Preparation special-item module maintains TLC sample tubes in the shelf stock
  boxes; the robot bench is robot-internal parking and is not chemist-maintained.
- TLC selection and dispatch use tubes in ONE shelf sample-tube box: 2–4 tubes, one row,
  contiguous columns, starting at column 1.
- A dispatched TLC task's carry coordinates for the sample box, solvent box, and tip boxes match
  those items' recorded inventory placements.
- The Consumable Maintenance page cannot edit specific (`有特殊性`) items; shelf sample-tube stock
  is read-only there.
- Selecting an item for a task never creates inventory; empty slots/cells change only in
  maintenance mode.
- TLC readiness does not depend on placeless placeholder records such as staining jar or
  eluent tube pair.
- TLC tip boxes exist as physical inventory with concrete locations before execution, and execution
  allocation selects existing tip-box IDs rather than creating inventory rows.
- TLC waste-tip bins exist as physical inventory with concrete locations.
- Robot-executed steps are dispatched through Lab Service / Nexus.
- AI parameter recommendations and result analyses consumed by the product come from
  ChemEngine; ChemEngine failures surface as visible errors, never as silently
  substituted results.
- Image evidence sent to ChemEngine is transferred via presigned URLs that ChemEngine
  can reach in the target deployment.
- RE realtime result analysis comes from the Robot Team's Mars system, not ChemEngine.
- Manual steps are represented as human-owned work and are not silently treated as robot-completed.
- Result evidence remains visible in the portal after it is produced.
- Agent behavior that is specific to backend copilot reasoning remains documented in `BIC-agent-service/docs/project-prd.md`.

## Out of Scope

- Backend-only implementation details that do not change product behavior.
- Agent prompt/tool internals except where they define externally visible copilot behavior.
- Cross-team shared protocol governance owned by `BIC-shared-types`.

## Dependencies / Open Questions

- Detailed production acceptance criteria for each chemistry stage should be expanded as product decisions are finalized.
- The former open questions on TLC tube quantity and slot-assignment semantics are RESOLVED
  (2026-07-05): see rules 8 and 9 under Experiment Item Management Rules.
- Pending external follow-up: the Feishu interaction document and 实验室信息维护配置表 must be
  corrected at source — the `1 or 2` tube quantity and click-empty-slot assignment statements are
  superseded, and a note should record that the robot fetches the sample-tube box from the shelf
  with system-resolved coordinates (no new 配置表 row needed; bench parking is robot-internal).

## Related Project PRDs

- Agent Service Project PRD: `BIC-agent-service/docs/project-prd.md`
- Agent Portal Lab Logistics Project PRD: `BIC-agent-portal/docs/project-prd.md`

## Change Log

- 2026-07-05: Consistency pass after implementation — config source scope excludes robot-internal
  parking slots; the 配置表 follow-up no longer asks for a bench-box row.
- 2026-07-05: Added requirement 8 (AI-engine backed intelligence): ChemEngine (Algo
  Team) as the authority for parameter recommendation / result analysis, presigned-URL
  image transfer with dual AWS-S3/MinIO store support, Mars (Robot Team) ownership of RE
  realtime analysis, and matching acceptance criteria. Backend transport behavior
  (mock/real switch) is refined in the Agent Service Project PRD.
- 2026-07-05: Revised rule 7 per the robot protocol (mars_doc tlc-api-reference): the chemist
  maintains AND selects sample tubes on the supply shelf; the robot carries the 2ml/50ml/tip
  boxes shelf→bench itself with coordinates resolved from inventory placement; bench = robot
  parking. Acceptance criteria updated to match.
- 2026-07-05: Closed the tube-quantity (2–4 confirmed) and assignment-semantics
  (maintain-then-select) open questions; added the TLC shelf-stock / bench-dispatch-box inventory
  model, two-tier specificity terminology, and matching acceptance criteria.
- 2026-07-05: Added material preparation/consumable maintenance separation, task material card responsibilities, auto-pick confirmation rules, and open questions from the Feishu interaction document.
- 2026-07-05: Added TLC physical inventory integrity rules for location/containment validity, tip boxes, waste-tip bins, developing tanks, and removal of invalid readiness placeholders.
- 2026-07-05: Expanded generic consumable and experiment-specific lab item maintenance rules.
- 2026-07-05: Added core experiment concepts, TLC execution flow, item management rules, and TLC Lab Logistic UI requirements.
- 2026-07-05: Reframed this file as the business Production PRD and moved PRD-governance guidance to the `prd` skill.
