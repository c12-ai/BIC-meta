# BIC Production PRD

## Status

- Owner: Drake
- Review state: Draft
- Last updated: 2026-07-07

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

8. **Lab-state query entrance**
   - The chemist must be able to ask natural-language questions about the current lab, active experiments, robot state, lab tasks, inventory, containers, locations, failures, and results from the same copilot surface.
   - Query behavior is read-only. It must not dispatch execution, confirm a form, mutate inventory, or advance the workflow.
   - Broad lab-state questions, such as "how are the lab consumables" or "what is happening in the lab", should receive a useful summarized answer instead of being rejected solely because the user did not provide a concrete object ID.
   - Fine-grained questions, such as whether a specific tube, slot, robot, container, rack, or workspace position exists or is occupied, should be answered from Lab Service state whenever the required data is available.

9. **Intent routing and query boundaries**
   - The copilot must distinguish read-only query requests from execution, confirmation, revision, design, and clarification turns.
   - Execution-like requests must not be silently routed to the read-only Query Agent.
   - Clarification or missing-input turns must remain in the relevant form or specialist workflow instead of being treated as lab-state queries.
   - Query routing should be context-aware enough to support user phrasing in both broad and specific forms.

10. **Human-friendly state reporting**
    - Lab-state answers must be composed for chemists, not emitted as raw service logs.
    - Robot, task, location, and inventory status should be described in natural language.
    - Internal IDs may be included when they help locate a real object, but readable names and real lab positions should be primary when available.
    - The copilot must not invent missing lab state. If a source is unavailable or a queried object cannot be found, it should say what was checked and what remains unknown.

11. **Long-session continuity**
    - The copilot must remain coherent across long sessions with many prior messages, tool calls, and form interactions.
    - Context compression, summary, and token-budget behavior must preserve the current objective, workflow stage, user-confirmed facts, pending form state, and recent lab execution context.
    - The user should not see repeated narration, stale form assumptions, or irrelevant tool detail caused by context overflow.

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

## UI Interaction Requirements

For the TLC Lab Logistic panel:

- The panel should display TLC-specific Lab Logistic parameters after TLC Parameter Design is confirmed.
- The right side of the panel should show empty sample tube positions for the TLC-relevant slots.
- The user must be able to use this panel to confirm the concrete sample tube placement needed for TLC execution.

For lab-state and inventory reporting:

- Query Agent answers about consumables, racks, workspaces, and containers must align with the same source-of-truth counts shown in the portal.
- When the portal displays a count as `X/Y`, the copilot may report that count as the front-end display count but must not reinterpret it as remaining capacity, fullness, depletion, or availability unless the underlying source explicitly defines that meaning.
- TLC workspace questions should distinguish the left robot workspace positions from the right material areas.
- TLC workspace reports should include human-readable position labels such as operating bench and disposal area when available.
- Consumable-maintenance rack reports should match the rack/floor/material grouping presented in the portal.

## Agent Copilot Upgrade Requirements

The current product direction includes a larger Agent Copilot upgrade beyond the first published `main` behavior.

1. **Query Agent**
   - Query Agent is the read-only entrance for lab-state questions.
   - It should combine current session context with Lab Service state and return an LLM-composed natural-language answer.
   - It should support broad overviews, active-task status, robot status, lab inventory, rack/workspace/container status, failure explanations, result lookups, object lookup, and location/occupancy lookup.
   - It should support fine-grained lab object queries at the level of a robot, tube, tube box, slot, rack position, workspace position, or container where the source data exists.

2. **Classifier refinement**
   - The problem-analysis / intent-classification stage must apply stricter boundaries before specialist routing.
   - Read-only questions should route to Query Agent.
   - Execute, confirm, revise, design, and clarify turns should route to their owning workflow or specialist instead of Query Agent.
   - Rule-first handling is acceptable where it prevents unsafe or visibly wrong routing, with model fallback used for ambiguous language.

3. **Lab-source alignment**
   - Query Agent must treat Lab Service as the authority for live lab state.
   - Portal-visible inventory summaries must use the same Lab Service endpoints and semantics as the corresponding portal surfaces.
   - Robot location IDs should be resolved to readable laboratory locations when Lab Service provides that mapping.
   - Error payloads from Lab Service should be preserved well enough for user-facing failure summaries.

4. **Conversation and context management**
   - Long-running sessions should use token accounting, context trimming, rolling summaries, and tool-result compaction so the copilot can keep working without losing the user's current goal.
   - Context management must prioritize human-confirmed product state over verbose tool output.
   - The copilot should avoid duplicate adjacent narration and stale repeated assistant text.

5. **Objective and form continuity**
   - Objective handling should prefer the form-first product flow when the user is in an objective or parameter collection phase.
   - User-provided form values should remain synchronized with the specialist workflow.
   - The copilot should use prior-turn context when deciding whether a user message is admissible or relevant to the current chemistry workflow.

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
- TLC experiment design lets the user select sample tubes for the current experiment.
- CC experiment design lets the user select the sample column for the current experiment.
- The TLC Lab Logistic panel shows empty sample tube positions for TLC-relevant slots.
- Robot-executed steps are dispatched through Lab Service / Nexus.
- Manual steps are represented as human-owned work and are not silently treated as robot-completed.
- Result evidence remains visible in the portal after it is produced.
- Agent behavior that is specific to backend copilot reasoning remains documented in `BIC-agent-service/docs/project-prd.md`.
- A broad lab-state query receives a useful summary instead of a demand for a specific ID when the relevant lab data exists.
- A fine-grained query can answer robot, object, slot, tube, rack, workspace, or location questions from Lab Service state.
- Query answers are natural-language reports composed from read-only facts, not raw `key=value` dumps.
- Robot location and workspace reports prefer readable lab names over internal location IDs when such names are available.
- TLC workspace reports distinguish left robot workspace occupancy from right material-area display counts.
- Inventory reports preserve portal count semantics such as `X/Y` without converting them into unsupported "remaining" or "full" claims.
- Intent classification keeps execution, confirmation, revision, design, and clarification turns out of Query Agent.
- Long sessions preserve the current objective, workflow stage, confirmed facts, and pending form state despite context size growth.
- Copilot replies do not repeat stale adjacent narration caused by context rehydration.

## Out of Scope

- Backend-only implementation details that do not change product behavior.
- Agent prompt/tool internals except where they define externally visible copilot behavior.
- Cross-team shared protocol governance owned by `BIC-shared-types`.

## Dependencies / Open Questions

- Detailed production acceptance criteria for each chemistry stage should be expanded as product decisions are finalized.
- Lab Service should continue exposing readable location labels for internal IDs that appear in robot, workspace, and inventory data.
- Portal and Lab Service should keep inventory count semantics documented so Query Agent can report them without inventing availability meaning.

## Related Project PRDs

- Agent Service Project PRD: `BIC-agent-service/docs/project-prd.md`

## Change Log

- 2026-07-07: Added Agent Copilot upgrade requirements for Query Agent, intent routing, lab-state reporting, context continuity, and portal-aligned inventory semantics.
- 2026-07-05: Expanded generic consumable and experiment-specific lab item maintenance rules.
- 2026-07-05: Added core experiment concepts, TLC execution flow, item management rules, and TLC Lab Logistic UI requirements.
- 2026-07-05: Reframed this file as the business Production PRD and moved PRD-governance guidance to the `prd` skill.
