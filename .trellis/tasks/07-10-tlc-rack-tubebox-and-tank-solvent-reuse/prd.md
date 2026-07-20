# TLC rack tube-box surface + developing-tank solvent reuse

## Goal

Two related TLC lab-model corrections, from Drake (2026-07-10):

1. **R1 — Tube boxes live on the TLC rack, not the TLC workbench.** On the TLC
   workbench the chemist controls ONLY the developing-tank lid, the developing
   tank, and silica plates; everything else on the workbench is robot territory.
   Therefore when the chemist selects / inserts sample tubes into tube boxes
   during TLC experiment design, they are managing a tube box on the **TLC rack**
   (chemist shelf surface), never a workbench box. The portal Consumable
   Maintenance page must reflect the same area model.

2. **R2 — Developing tank contents become first-class inventory properties, and
   the planner reuses matching tanks.** Today the user tells the system a
   developing tank sits on a dedicated workbench slot, but the system stores
   nothing about its contents — every tank is assumed empty, so the robot always
   runs the 配液 (solvent preparation) step: pick solvent from the 50 ml tubes,
   dispense into the tank.
   - Store the tank's contents (solvent system + ratio) in the `properties`
     column of `tlc_inventory` — the same mechanism as sample-tube purity
     (`exp_id` / `exp_name` / `purity`).
   - Before generating the 配液 step, the TLC planner first looks up workbench
     developing tanks for one whose recorded contents MATCH the run's target
     developing solvent system. If found: the robot just picks & drops that tank
     into place and skips solvent prep. If none match: prep the solvent as today.

## Decisions (Drake, 2026-07-10)

- **D1 (match rule):** a tank matches only on EXACT normalized solvent
  components AND exact ratio. No tolerance band, no chemistry judgment in code.
- **D2 (contents source):** developing-tank contents exist ONLY in seed/reset
  test data for now. There is NO chemist declaration entry point yet — no
  Consumable Maintenance form, no Lab Logistics field. (Future task.)
- **D3 (no write-back):** after a robot 配液 run, the system does NOT record the
  prepared contents on the tank row. Robot-prepped tanks stay unrecorded.
- **D4 (tank used where it stands):** verified in code — the develop (immerse)
  step addresses the tank at its own workbench slot; the tank's AGV ride exists
  only for filling. A matched tank is therefore used in place: the planner binds
  its slot and emits NO tank/lid movement before immerse. This supersedes the
  literal "pick and drop" wording in the original request.
- **D5 (round-1 carries unchanged):** when fill is skipped, round 1 still
  carries all four boxes (incl. the unused 50 ml solvent box + 1250 µl tips)
  from the shelf — keeps carry/END_TLC choreography symmetric and the diff
  surgical. Confirmed by the Robot-team agreement of 2026-07-11 (four-box
  carry + reusable-tank check).
- **D8 (lid presentation, Drake 2026-07-11):** ratify portal #29 — the
  maintenance UI shows only developing tank + silica plate; the tank lid stays
  in the workspace API response read-only (`is_maintainable=False`) and the
  portal hides it. Lids are not inventory (they sit on their tanks), so there
  is nothing to maintain.

## Requirements

### R1 — TLC rack as the tube-box surface

- The lab material configuration must place TLC sample-tube boxes on the TLC
  rack area; the TLC workbench area must contain only robot-territory items plus
  the three chemist-controlled items (developing tank, tank lid, silica plates).
- Lid presentation (D8): the tank lid stays in the workspace API model as a
  read-only area, but is NOT a maintenance surface — the portal hides it
  (landed in portal #29 together with the tube-box/tip-box hiding).
- The TLC insert-and-assign surface (Lab Logistics right panel, PRD rule 8)
  renders the rack tube boxes — no workbench tube boxes exist to render.
- The portal Consumable Maintenance page must present the same split: tube-box
  stock appears under the rack area (read-only for specific items per Production
  PRD rule 7), and the workbench does not present tube boxes.
- Robot carry coordinates for the sample-tube box (Production PRD rule 7:
  resolved from recorded inventory placement) must keep working with rack
  placements.

### R2 — Developing tank contents + planner reuse

- `tlc_inventory` rows for developing tanks can carry a properties bag
  describing contents: the solvent system (components) and ratio. Absent
  properties = unknown/empty tank (today's semantics; still valid and the
  default for anything not seeded).
- Seed/reset test data includes at least one workbench developing tank WITH
  recorded contents and one without, so both planner branches are exercisable
  on the bench.
- Planner behavior at 配液: prefer a workbench developing tank whose recorded
  contents exactly match the run's target solvent system + ratio (D1) when
  binding the tank; when the bound tank matches the round's param, emit NO
  solvent-prep ops and use the tank at its own slot (D4); otherwise emit
  today's full solvent-prep sequence (unchanged).
- Tank allocation is tiered (**D6, ratified by Drake 2026-07-10**): exact-match
  tank → tank with no recorded contents (solvent prep MUST target an empty
  tank) → fail loud. A contents-bearing tank that does NOT match the target is
  never bound for a prep round — the robot must not dispense into a tank
  recorded as full.
- Within a tier, tanks are picked LEFT TO RIGHT by slot position (**D7, Drake
  2026-07-10**) — ascending slot index, never sorted by object id.
- No chemist-facing declaration or editing surface in this task (D2), and no
  post-run write-back (D3). The properties shape must still be designed so the
  future declaration entry point can adopt it without migration.

## Constraints

- Production PRD rule 6 (TLC physical inventory integrity) and rule 7 (shelf is
  the chemist surface; robot carries) still hold; this task refines WHERE the
  tube boxes live and WHAT the tank rows say, not the integrity rules.
- Tank-contents properties are consumed by planner matching (and later portal
  display / reporting) — never sent to ChemEngine (mirrors the purity-properties
  precedent).
- Per repo rule 10: contract or config-shape changes require same-changeset spec
  updates under `.trellis/spec/`, and the Production PRD needs a matching edit
  (area model refinement + tank-contents rule + planner reuse behavior).

## Open Questions

None blocking. Robot-team status (Drake agreement, 2026-07-11): the initial
prep phase CONCEPT is agreed — the robot carries all four boxes (confirms D5)
and a reusable-tank check is added; on a match the dispatch sends no
solvent-prep ops. Remaining external follow-up: op-level verification of the
exact fill-skipped program via the `feat/tlc_following_phase` proposal flow
(op list → feasibility → sequencing → approval); the concrete op list ships
labeled as BIC proposal until then (design.md risk flag, implement D4).

Resolved, for the record:

- **OQ-4 RESOLVED:** the rack surface is already correct (Material Prep uses
  `source=storage`; rack tube boxes already seeded on the supply shelf). The
  offending surface is the consumables-page TLC Workspace section, whose
  chemist shelves expose tube boxes + tip box (`preparation_service.py:138-163`)
  — R1 = trim that response + remove the portal's now-dead box-grid override.
- **OQ-5 RESOLVED:** the format is structured at every hop — `solvents:
  list[Solvent]` (StrEnum PE/EA/DCM/MeOH) + `solvent_ratio: list[int]`
  (`bic_shared_types/common/tlc.py:27`). Tank properties mirror it verbatim:
  `{"solvents": ["PE", "EA"], "solvent_ratio": [3, 1]}` — exact list equality,
  no parsing.

## Acceptance Criteria

- [ ] Lab material configuration and seed/reset data place TLC sample-tube boxes
      on the TLC rack; no tube-box slots exist on the TLC workbench.
- [ ] The TLC workbench API model exposes exactly three chemist-controlled item
      kinds — developing tank, developing-tank lid (read-only), silica plates —
      while the portal maintenance surface shows only tank + silica (D8, landed
      in portal #29).
- [ ] Portal Consumable Maintenance renders tube-box stock under the rack area
      and never under the workbench; the TLC Lab Logistics right panel keeps
      working against rack boxes (insert-and-assign unchanged).
- [ ] Robot dispatch carry coordinates for the sample-tube box resolve from the
      rack placement.
- [ ] A developing-tank inventory row can persist contents (solvent system +
      ratio) in `tlc_inventory.properties`; rows without the property behave as
      unknown/empty (current behavior preserved).
- [ ] Seed/reset data contains a contents-bearing tank and a contents-less tank.
- [ ] Given a workbench tank whose recorded contents exactly match the run's
      target solvent system + ratio, the planner binds that tank's slot and
      emits NO 配液 fill ops (no lid-off/tank-to-AGV/pipette/aspirate/dispense);
      the run develops in the matched tank at its own slot (D4).
- [ ] Given no matching tank, the run binds a contents-less tank and the
      planner emits today's full solvent-prep sequence — for an identical
      spec, op output is identical to the pre-change golden (planner-level
      regression). Note: the BOUND SLOT may deliberately differ from today's
      id-ordered pick (tier rule skips contents-bearing tanks).
- [ ] Given only contents-bearing non-matching tanks, dispatch fails loudly
      (no silent dispense into a full tank).
- [ ] Given multiple eligible tanks in the same tier, the leftmost one (lowest
      slot index) is picked — object id never decides (D7).
- [ ] No portal input surface for tank contents is added (D2), and no write-back
      occurs after 配液 (D3).
- [ ] Spec docs under `.trellis/spec/` and the Production PRD are updated in the
      same change set for the area-model and tank-contents changes.

## Notes

- Portal #29 (`37dbc69f`, c12-syq, landed 2026-07-11) shipped the FE-side
  workspace hiding (tube boxes / tip box / lid / robot zones) + sample_tube
  read-only ahead of this task — the portal phase shrinks to contract cleanup
  (see implement.md Phase B).
- Research findings land in `research/` (lab-service.md, portal.md, contract.md).
- Complex task: `design.md` + `implement.md` required before `task.py start`.
- Future follow-ups deliberately out of scope: chemist declaration entry point
  for tank contents, robot write-back after 配液, staleness/expiry of prepared
  solvent, portal display of tank contents.
