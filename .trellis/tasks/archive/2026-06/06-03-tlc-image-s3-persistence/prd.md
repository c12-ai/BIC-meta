# TLC Image S3 Persistence (AWS S3 China)

## Goal

Switch BIC-agent-service from local MinIO to **AWS S3 China (`cn-northwest-1`, bucket `aichemengine-release-bundles`)** as the storage backend for TLC plate images, so dev (and later staging/prod) persist plate images on real cloud storage. The FE upload pipeline, `MindClient`, and the recognize handler stay unchanged — this is an **infrastructure config swap**, not a feature build.

## Scope Decision (locked)

**Approach #1 — Just point dev at AWS S3.** Flip env vars, verify the existing presign → PUT → presign → recognize round-trip works end-to-end against AWS S3 China. No coexistence mode, no client factory, no production-grade IAM rework in this task.

## What I already know (from repo inspection)

**The upload pipeline already exists end-to-end:**

- FE `TlcUploadControl.tsx` → `uploadAndAnalyzeTlc` in `BIC-agent-portal/src/lib/tlc-client.ts`
- FE flow: `presignFile(put)` → S3 PUT direct from browser → `presignFile(get)` → POST `/sessions/{id}/tlc/recognize` with the GET URL
- BE presign endpoint: `SessionService.request_presigned_url` (`app/session/service.py:334`) → `MinIOClient.generate_presigned_url(bucket=settings.s3_bucket_name, …)`
- BE recognize: `POST /{session_id}/tlc/recognize` → `FastPathHandlers.handle_tlc_recognize` → `MindClient.recognize_tlc_plate(tlc_image_url=…)`
- Session-prefix gate: file_key must start with `${sessionId}/`
- TLC image URL persisted in `agent_tasks.spec.tlc_image_url` + emitted as `TLCRecognizedEvent`

**Current storage config (`.env`)**:
```
S3_ENDPOINT_URL=http://localhost:9000       # MinIO local
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=bic_local_dev
S3_REGION=us-east-1
S3_BUCKET_NAME=tlc-images
```

**Target AWS S3 (verified by CLI):**
- Account: `432084094746` (aws-cn partition)
- IAM user: `zhouyuxuan` (Drake's personal, dev only)
- Bucket: `aichemengine-release-bundles`
- Region: `cn-northwest-1`
- Versioning ON, SSE-S3 AES256, public access blocked
- CORS: `PUT`/`GET` from `*` allowed
- Existing objects show this bucket already holds TLC-like images at root (`...-tlcimage.jpg`, `...-demo.jpeg`)

## Requirements

1. `BIC-agent-service/.env` updated so the running service uses AWS S3 China credentials and the `aichemengine-release-bundles` bucket.
2. `S3_ENDPOINT_URL` is **empty/unset** so boto3 resolves the regional AWS S3 China endpoint automatically (no MinIO endpoint override).
3. Object keys remain under the session-prefix gate (`<session_id>/<file_key>`). Decision needed: do we add an additional `bic/tlc/` prefix on top to namespace within the shared bucket? See Open Q1.
4. Existing presign Facade (`SessionService.request_presigned_url`) keeps its current contract — no signature, response shape, or error semantics change.
5. FE `uploadAndAnalyzeTlc` works unchanged against the new presigned PUT/GET URLs.
6. `MindClient.recognize_tlc_plate` succeeds with the AWS-S3-China presigned GET URL (vision provider can fetch the URL).
7. `.env.example` updated with placeholder values and a comment block noting AWS S3 China usage.
8. Local docker-compose path (MinIO) is **not removed** — Drake can revert by restoring the four env vars. No code path is deleted.

## Acceptance Criteria

- [ ] AC1: `.env` points at AWS S3 China; `S3_ENDPOINT_URL` is empty.
- [ ] AC2: `aws s3api head-object --bucket aichemengine-release-bundles --key <session_id>/<some_key>` returns the object after a successful FE upload.
- [ ] AC3: Manual e2e — open BIC portal, upload a TLC plate image, hit recognize, see Rf values rendered. The image URL stored on `agent_tasks.spec.tlc_image_url` resolves to an `https://aichemengine-release-bundles.s3.cn-northwest-1.amazonaws.com.cn/...` path.
- [ ] AC4: `tests/integration/test_routes_tlc.py` still passes (uses mocks, should be untouched).
- [ ] AC5: `.env.example` updated; reverting four env vars restores MinIO local-dev mode.

## Definition of Done

- AC1–AC5 all satisfied
- Lint / typecheck / pytest green for BIC-agent-service
- Drake performs manual e2e once
- A short note in the task's `notes.md` documenting the bucket name + how to revert to MinIO

## Out of Scope (explicit)

- Migrating existing MinIO objects to AWS S3.
- Changing MindClient / recognition model / `handle_tlc_recognize` behavior.
- Production-grade IAM hardening (dedicated `bic-agent-service` IAM user with least-privilege policy) — tracked separately.
- Adding new persistence tables or contract changes.
- Object-key prefix changes BEYOND the session-prefix gate (unless answered "yes" to Open Q1).
- Tightening CORS allowed-origins on the bucket.
- Removing or refactoring `MinIOClient` — keep as the S3-compatible client (boto3 doesn't care).

## Decision (ADR-lite)

**Context**: The bucket `aichemengine-release-bundles` is shared with other teams. We needed to decide whether to namespace BIC objects under a `bic/tlc/` prefix.

**Decision**: **Option B — no extra prefix.** Keep the existing session-prefix gate (`<session_id>/<filename>`). Session IDs are UUIDs, so collision risk is zero.

**Consequences**:
- Pure infra swap — no FE `fileKey` builder change, no BE session-prefix gate change, no contract/spec change.
- BIC objects sit at bucket root alongside other teams' objects. Acceptable because the bucket is already used this way today.
- Rule 2 (simplicity first) + Rule 3 (surgical changes) satisfied.
- Future namespacing (if a team needs it) can be added cleanly as a follow-up — would require updating `backend-contract.md` + `facade.md` at that time.

## Open Questions (resolved)

1. ~~**Vision provider reachability to AWS S3 China.**~~ **Resolved (2026-06-03 via trellis-check):** MindClient's vision provider successfully fetched `*.s3.cn-northwest-1.amazonaws.com.cn` presigned GET URLs — confirmed by two Playwright sessions whose `POST /tlc/recognize` returned 200 with `tlc_recognized` events emitted. Not a blocker.

## Verified

trellis-check sub-agent ran V2–V7 (2026-06-03) and reported ALL GREEN:
- V2 aws-cli sanity ✅ — round-trip on `aichemengine-release-bundles`
- V3 presign smoke ✅ — URL host = `aichemengine-release-bundles.s3.cn-northwest-1.amazonaws.com.cn`
- V4 raw PUT ✅ — 200 OK, SSE=AES256, ETag returned
- V5 Playwright e2e ✅ — backend logs show both T2/T3 `POST /tlc/recognize` returned 200; spec form rendered Rf values. T2 reported a test-side `page.on('response', ...)` listener race (NOT a config-swap failure — tracked as a separate follow-up).
- V6 vision-provider reachability ✅ — verified inline via V5 success
- V7 cleanup ✅ — all 4 test objects deleted (bucket versioning ON → delete-markers only)

AC1 ✅ · AC2 ✅ · AC3 ✅ · AC4 ✅ (V1) · AC5 ✅ (V1)

**Follow-up flagged (out of scope):** `BIC-agent-portal/tests/tlc-upload-chain.spec.ts` T2 has a flaky `page.on('response', ...)` listener — should be addressed in a separate task.

## Technical Notes

**FE entry points:**
- `BIC-agent-portal/src/lib/tlc-client.ts:84` `uploadAndAnalyzeTlc` — full pipeline
- `BIC-agent-portal/src/components/workspace/TlcUploadControl.tsx` — UI control

**BE entry points:**
- `BIC-agent-service/app/api/routers/files.py` — `POST /sessions/{id}/files/presign` route (verified by trellis-check)
- `BIC-agent-service/app/session/service.py:334` `request_presigned_url` — presign Facade (session-prefix gate)
- `BIC-agent-service/app/session/fast_path_handlers.py:468` `handle_tlc_recognize`
- `BIC-agent-service/app/infrastructure/s3_client.py` — boto3 wrapper (`MinIOClient`)
- `BIC-agent-service/app/infrastructure/mind_client.py` — vision RPC

**Config files:**
- `BIC-agent-service/.env` — runtime config
- `BIC-agent-service/.env.example` — committed template

**Spec/contract files (consulted for this change):**
- `BIC-agent-service/.trellis/spec/backend/L4/clients.md` — S3 client conventions
- `BIC-agent-service/.trellis/spec/backend/L2/facade.md` — `SessionService` presign contract
- `BIC-agent-service/.trellis/spec/backend/L1/http-routes.md` — `/sessions/{id}/presign` route
- `BIC-agent-portal/.trellis/spec/backend-contract.md` — FE↔BE presign contract

**AWS-CN partition gotcha:**
- ARNs use `arn:aws-cn:s3:::*` (not `arn:aws:s3:::*`).
- boto3 auto-handles this from `S3_REGION=cn-northwest-1` — no code changes needed.
- Presigned URL host is `*.s3.cn-northwest-1.amazonaws.com.cn` (note the `.cn` suffix).

**Contract surface — NONE CHANGED.** No FE↔BE, no L1↔L2↔L3↔L4, no service-to-service contract is altered. Rule 10 satisfied: no spec update required for an infra-only config swap, unless we answer "yes" to Open Q1 (key-prefix change), in which case `backend-contract.md` + `facade.md` must be updated in the same change set.
