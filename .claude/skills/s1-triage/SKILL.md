---
name: s1-triage
description: S1 triage role of the agent-improvement workflow — receive user test feedback, reproduce it on the bench with evidence, and file an issue in c12-ai/BIC-meta per the template. Triggers when the user reports an agent problem, asks to triage / file / organize a report, or says /s1-triage.
---

# S1 — Feedback triage / reproduce / file

First read `ops/agent-improvement-workflow.md` (role boundaries, issue template, bench playbook, severity labels).

## Responsibilities

After the user hands over a piece of feedback (screenshot / description / session link):

1. **Reproduce with evidence** (backend truth first, do not trust the page):
   - Take the session_id from the URL → `docker exec talos-postgres psql -U postgres -d talos_agent_db`
     and query `session_events` (seq/kind/payload), `plans.current_job_id`, `trials`.
   - When needed, read the BE log `talos/BIC-agent-service/app/logs/error.log` and tmux pane output.
   - ⚠️ Read-only. Do NOT reset, do NOT restart services, do NOT run test loops that write the DB (the user is testing).
2. **De-dup**: compare against `gh issue list --repo c12-ai/BIC-meta --state open`; if it already exists, comment the new evidence onto that issue instead of filing a duplicate.
3. **File**: write the body per the SOP issue template (symptom / evidence / repro / root-cause hypothesis / **binary acceptance is mandatory**), run `gh issue create --repo c12-ai/BIC-meta`, and apply the severity + repo + `needs-triage` labels.
4. Reply to the user: issue number + one-line classification + suggested next step (go to S2, or batch it).

## Prohibited

- Do NOT change product code; do NOT draw root-cause conclusions (a hypothesis is fine — label it "hypothesis").
- Do NOT silently downgrade or merge-dilute a problem — if unsure about severity, ask the user.
