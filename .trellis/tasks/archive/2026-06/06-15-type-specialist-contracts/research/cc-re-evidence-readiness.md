# Research: CC/RE typed result-review wire — evidence readiness

- **Query**: Does the CC/RE executor pipeline today carry enough structured data to fill the FE's typed `CcEvidence` / `ReEvidence` shapes, or is the data simply not there (typed wire would be hollow / still need fixtures)?
- **Scope**: mixed (FE + BE + shared-types + lab-service)
- **Date**: 2026-06-15

## TL;DR VERDICT

**(c) BLOCKED — the source data does not exist yet, in two different ways.**

1. **CC**: The target shape (`CcEvidence`) maps almost 1:1 onto a *Mind AI analysis* type that already exists in shared-types (`CCResult.uv_inspection` — peaks, tube ranges, areas, roles). BUT the BE **never calls Mind** — `_analyze_result` unconditionally raises `MindCallError` and emits a hardcoded `{"status":"deferred"}` placeholder (`tools.py:516-530`). So the typed CC fields are *defined upstream* but **never populated** end-to-end. CC is "fillable in principle, but the entire production path is stubbed out — needs the deferred Mind call wired first."
2. **RE**: Worse. The target shape (`ReEvidence.checkpoints` — bath temp / pressure / rotation / endpoint observations) has **no corresponding structured field anywhere**. The only RE result type is `REResult` = a single `result: REResultStatus` enum (ongoing/finish/fail) (`mcp_protocol/re.py:34-37`), and the raw RE data is just timestamped droplet photos (`common/re.py:36-48`). The robot/lab never emits temperature/pressure/rotation/endpoint observations. RE is **MISSING-AT-SOURCE**.

Both executors today emit the *identical* placeholder analysis dict, and the FE already renders evidence entirely from fixtures (`result-stage-model.ts:5-11`, `result-stage-adapters.ts`). The live `analysis` dict attaches only as opaque `raw` to one card. So the typed wire, if shipped against today's data, would be **hollow** for both CC and RE.

---

## Findings

### A. What the FE expects (target schema)

#### `CcEvidence` — `result-stage-model.ts:83-92`
| Field | Type | Notes |
|---|---|---|
| `kind` | `'cc'` | literal tag |
| `rackCols` | `number` | rack grid width (fixture: 5) |
| `rack` | `RackTube[]` | `{ label: string; status: 'product'\|'suspect'\|'waste'\|'idle' }` (`:67-73`) — per-well tube map |
| `rackAlt` | `string` | a11y label |
| `rackCaption` | `string` | e.g. "5 × 15 test tube rack, serpentine layout" |
| `uvTraceLabel` | `string` | UV trace caption |
| `fractions` | `FractionRow[]` | `{ peak; tubes; time; area; status }` (`:75-81`) — per-peak summary |

#### `ReEvidence` — `result-stage-model.ts:139-142`
| Field | Type | Notes |
|---|---|---|
| `kind` | `'re'` | literal tag |
| `checkpoints` | `ReCheckpointRow[]` | `{ checkpoint; target; observed; statusLabel; ok }` (`:131-137`) |

#### Realistic fixture data volume — `result-stage-fixtures.ts`
- **CC fixture** (`:64-97`): `rackCols:5`, a 20-well `rack` array with product (42–44) / suspect (51–53) / waste (63–65) / idle wells, plus 3 `fractions` rows (Peak 1/2/3 with retention time + UV area + status).
- **RE fixture** (`:194-225`): 4 `checkpoints` — Bath temperature (35 °C), Pressure (120 mbar / observed 118–122), Rotation speed (90 rpm), Endpoint (Dry residue). Each row is a target-vs-observed comparison with `ok` boolean.

### B. What the BE produces today (source data)

#### The CC + RE analyze tools share ONE stubbed core
- `analyze_cc_result` (`tools.py:930-948`) → `return await _analyze_result(state, runtime, mind, "cc")`
- `analyze_re_result` (`tools.py:1221-1232`) → `return await _analyze_result(state, runtime, mind, "re")`
- `_analyze_result` (`tools.py:501-555`): the `try` block at `:516-518` **unconditionally** does `raise MindCallError(...)` ("real Mind call deferred (ticket follow-up)"). The `except` (`:519-530`) sets:
  ```python
  analysis_payload = {
      "status": "deferred",
      "notice": "Mind analyze call deferred; placeholder analysis returned.",
  }
  ```
  This is the **only** content ever placed into `TaskResultAnalyzedEvent.analysis` and the `result_review` form's `original_action.analysis` (`:534-550`). The `else`/`mind_succeeded=True` branch at `:531-532` is marked `pyright: ignore[reportUnreachable]` — i.e. dead code today.
- `TaskResultAnalyzedEvent.analysis` is itself typed `dict[str, Any] = {}` (`runtime_emitted.py:579`) — a free-form blob by design.

So **today's `analysis` dict has exactly two keys (`status`, `notice`)** and zero chemistry evidence. Identical for CC and RE.

#### Upstream data sources (where a real impl WOULD pull from)

- **`query_l4_status` → `lab.query_task_status()` returns `TaskRead`** (`lab_client.py:80-85`; `task_protocol/responses.py:54-69`). `TaskRead` fields: `id, task_type, status, params, steps[], current_skill_id, error_message, timestamps`. **No result-evidence at all** — `steps` are status+timestamps (`TaskStepRead`, `:16-27`); `params` is the *input* spec. So the BE's live read path from Nexus carries **no** fraction/peak/checkpoint data.

- **CC Mind response type — `CCResult`** (`mcp_protocol/cc.py:75-86`) — this is the rich one, but it's the Mind HTTP *response* the BE never requests today:
  - `pic_urls: list[FileUrl]`
  - `uv_inspection: list[CCPeakInspection]` where `CCPeakInspection` (`:48-72`) = `peak_id`, `area_under_curve: float|None`, `retention_time_min: float|None`, `role: SpotRole`, `spot_id`, `tubes: list[TubeRange]`, `solvents`. `TubeRange` (`:34-38`) = `rack_id: UUID` + `tube_position: list[int]`.
  - `result: TaskResult` (success/fail/unknown).
- **CC raw data — `CCExperimentData`** (`common/cc.py:85-90`) = only `pic_urls`. The structured peaks/tubes exist **only after** Mind analysis, not in raw lab data.

- **RE Mind response type — `REResult`** (`mcp_protocol/re.py:34-37`) = **only** `result: REResultStatus` (ongoing/finish/fail). The module docstring (`:8-11`, `:92-99`) states RE result analysis is "a Mars-side realtime inference path... **not** a current Mind HTTP result-protocol endpoint" and `REResultRequest` is "**not backed by a current Mind HTTP endpoint**" (`:70-78`).
- **RE raw data — `REExperimentData`** (`common/re.py:36-48`) = list of `{pic_url, timestamp}` droplet frames. **No** temperature / pressure / rotation / endpoint observations.

#### What the robot actually sends back (true source of truth)
- Robot → lab over MQ `#.result` → `RobotResult` = shared `SkillResult` (`skill_commands.py:97-105`): `code, msg, skill_id, skill_type, updates: list[EntityUpdate], images: list[CapturedImage]|None`.
- `updates` are **entity state mutations** (rack/flask/device/consumable states — `messages.py:99-109`), not chemistry evidence. `result_handler.py` stores them read-only and validates drift; it does not synthesize peaks/checkpoints (lab-service `docs/dataflow.md`, `result_handler.py:50,125`).
- CC fraction collection exists only as an **outbound command** (`exec_collect_cc_fractions`, input `collect_config: list[int]` tube indices — `command_tools.py:175-187`), not as a result with per-peak area/retention data.

### C. Gap tables (the deliverable)

#### CcEvidence gap table
| FE field | BE source (if any) | HAVE/PARTIAL/MISSING | Evidence file:line |
|---|---|---|---|
| `kind:'cc'` | constant, FE-side | HAVE | `result-stage-model.ts:84` |
| `rackCols` | derivable from rack/cartridge config; not in analysis dict | MISSING (today) | `CCResult` has no grid width; `tools.py:527` placeholder only |
| `rack[]` (per-well status) | `CCResult.uv_inspection[].tubes[].tube_position` + `role` → could synthesize | PARTIAL — type exists upstream, **never fetched** | `mcp_protocol/cc.py:63-68`; never called → `tools.py:516-530` |
| `rackAlt` / `rackCaption` | FE-rendered text; needs rack data first | MISSING (today) | depends on rack[] above |
| `uvTraceLabel` | from `CCResult.pic_urls` / peak apex | PARTIAL — upstream type only | `mcp_protocol/cc.py:55-62,82` |
| `fractions[].peak` | `CCPeakInspection.peak_id` (would map to "Peak N") | PARTIAL — upstream only | `mcp_protocol/cc.py:51` |
| `fractions[].tubes` | `TubeRange.tube_position` | PARTIAL — upstream only | `mcp_protocol/cc.py:38,67` |
| `fractions[].time` | `CCPeakInspection.retention_time_min` | PARTIAL — upstream only | `mcp_protocol/cc.py:55-62` |
| `fractions[].area` | `CCPeakInspection.area_under_curve` | PARTIAL — upstream only | `mcp_protocol/cc.py:52-54` |
| `fractions[].status` | `CCPeakInspection.role` (SpotRole) → map to product/suspect/waste | PARTIAL — upstream only | `mcp_protocol/cc.py:63`; enums.py:30-36 |

**CC summary**: the typed fields are *structurally sourceable* from `CCResult` — but `CCResult` is the Mind HTTP response the BE **never requests** (call is deferred, `tools.py:516-518`). The live `analysis` dict carries none of it. So every CC evidence field is effectively **NOT FILLABLE today**; it becomes fillable only after the deferred Mind result call is wired AND a `CCResult → CcEvidence` mapper (incl. `role→status` and rack-grid synthesis) is written. `rackCols` / `rackAlt` / `rackCaption` are FE presentation derived from rack data and have no direct upstream field.

#### ReEvidence gap table
| FE field | BE source (if any) | HAVE/PARTIAL/MISSING | Evidence file:line |
|---|---|---|---|
| `kind:'re'` | constant, FE-side | HAVE | `result-stage-model.ts:140` |
| `checkpoints[].checkpoint` (Bath temp/Pressure/Rotation/Endpoint) | no per-checkpoint observation type exists | **MISSING-AT-SOURCE** | `REResult` only has `result` enum — `mcp_protocol/re.py:34-37` |
| `checkpoints[].target` | RE *params* (`REParam.temperature_c`, `air_pressure[]`) exist as inputs | PARTIAL (targets only) | `common/re.py:27-33` |
| `checkpoints[].observed` | no observed temp/pressure/rotation stream | **MISSING-AT-SOURCE** | raw RE data = droplet photos only, `common/re.py:36-48` |
| `checkpoints[].statusLabel` | n/a — no observation to label | **MISSING-AT-SOURCE** | `REResult` carries no per-metric status |
| `checkpoints[].ok` | only an overall `REResultStatus` (ongoing/finish/fail) exists | **MISSING-AT-SOURCE** (per-checkpoint) | `mcp_protocol/re.py:37`; enums.py:47-52 |

**RE summary**: only the *targets* are recoverable (from the RE param spec). Every *observed* value, per-checkpoint status, and endpoint observation is **MISSING-AT-SOURCE**: the robot/lab emits no temperature/pressure/rotation telemetry, the raw data is droplet photos, and the only result type is a 3-value status enum whose own docstring says result analysis lives on a not-yet-built "Mars-side realtime inference path."

### Does lab-service emit the underlying data?
- **CC fraction/tube/rack**: lab-service models fraction *collection commands* and tracks rack/tube **entity states** (idle/mounted/used), not per-fraction UV-peak chemistry. The robot result (`SkillResult.updates`) carries entity-state updates + captured images, never peak areas / retention times. → CC evidence's *chemistry* content has no lab-service source; it would have to come from Mind AI analysis.
- **RE checkpoints**: lab-service has no temperature/pressure/rotation observation channel back from the robot for RE. `RobotResult` updates are equipment/material state + images. → RE checkpoint observations are **not produced at source**.

## Caveats / Not Found
- I did not find any code path (BE or lab-service) that has *ever* populated `analysis` with real chemistry data — the Mind call is deferred in every branch and `mind_succeeded` is statically unreachable (`tools.py:531-532`).
- `CCResult` is genuinely well-shaped for `CcEvidence`; the blocker is purely that the BE→Mind result call is unimplemented, not that the type is missing. If the project's MVP scope is willing to wire that one Mind call + a mapper, CC becomes (b) "fillable but needs plumbing." RE cannot reach (b) without a brand-new observation contract from the robot/Mars side — it is firmly (c).
- I did not trace the `take_photo` / `CapturedImage` path in depth; images exist on the wire (`SkillResult.images`) and could back an evidence *thumbnail*, but not the structured tables the FE shapes require.
