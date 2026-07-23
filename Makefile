# BIC one-shot environment — thin entry. All logic lives in scripts/bic-env/*.
# Coworker story: clone this repo, `make up`, done. `make doctor` explains the rest.
#
# Knobs (env or `make X=... target`):
#   STAGE=local|dev|prod   which stage to launch (default local — the bench
#                          convenience). Each service reads its own
#                          .env.<stage>; the orchestrator only selects + launches.
#   BIC_ROOT=/path      where the service repos live (default: autodetected —
#                       this repo if they're nested inside it, else its parent)
#   DRY=1               up/restart: print planned actions, change nothing
#   INFRA=1             down: also stop the shared docker infra
#   CHEM_DIR=/path INFRA_DIR=/path   override auto-detection

ENV := ./scripts/bic-env

# Stage axis (local | dev | prod). ENV above is the SCRIPTS DIR path, so the
# stage arg is STAGE= (not ENV=) to avoid collision. Default local.
STAGE ?= local

# Default BIC_ROOT resolution order: explicit env / make X=... > .bic-env
# machine pin (gitignored, see common.sh) > autodetect (nested: repos inside
# this repo; sibling: this repo cloned next to them). The pin exists because
# autodetect can land on a WRONG parent dir holding stale same-named repos
# (2026-07-10 incident: migrations ran from a stale checkout).
BIC_ROOT ?= $(shell . ./.bic-env 2>/dev/null; if [ -n "$$BIC_ROOT" ]; then echo "$$BIC_ROOT"; elif [ -d "$(CURDIR)/BIC-agent-service" ]; then echo "$(CURDIR)"; else echo "$(abspath $(CURDIR)/..)"; fi)
BIC_STAGE := $(STAGE)
export BIC_ROOT BIC_STAGE DRY INFRA CHEM_DIR INFRA_DIR

.DEFAULT_GOAL := help
.PHONY: help up pull update doctor quality-test-doctor quality-test-setup down \
        restart-lab restart-BE restart-portal restart-mock restart-chem

help: ## Show this help
	@echo "BIC env — one-shot local bring-up"
	@echo ""
	@echo "  make up STAGE=local   idempotent bring-up + self-heal (STAGE=local|dev|prod, default local; DRY=1 to preview)"
	@echo "  make pull      fast-forward all repos (meta/services/infra) to origin/main"
	@echo "  make update    pull + full restart on the new code (pull && up alone does NOT redeploy running services)"
	@echo "  make doctor    read-only full checkup (each red card has a fix command)"
	@echo "  make quality-test-doctor   read-only Phase 2 test runtime check"
	@echo "  make quality-test-setup    explicitly install Phase 2 project test runtime"
	@echo "  make down      stop app services (INFRA=1 also stops shared infra)"
	@echo "  make restart-<svc>   lab | BE | portal | mock | chem"
	@echo ""
	@echo "  Config lives in each repo's .env.<stage> — the orchestrator never writes it."
	@echo "  BIC_ROOT=$(BIC_ROOT)"
	@echo "  Troubleshooting appendix: ops/run-latest-2026-07-10.md"

## --- one-shot env ----------------------------------------------------------
up:            ; @$(ENV)/up.sh
pull:          ; @$(ENV)/pull.sh
# update = pull + restart everything on the new code. A bare `make pull && make up`
# on a RUNNING bench is safe but does NOT redeploy: up only heals unhealthy
# services, so BE/lab/mock keep executing pre-pull code (vite portal is the
# exception — it serves from disk). update closes that gap deterministically.
update:        ; @$(ENV)/pull.sh && $(ENV)/down.sh && $(ENV)/up.sh
doctor:        ; @$(ENV)/doctor.sh
quality-test-doctor: ; @./tools/bic-quality-kit/doctor-test-runtime.sh
quality-test-setup:  ; @./tools/bic-quality-kit/setup-test-runtime.sh --execute

## --- field (orin) ----------------------------------------------------------
# Field counterparts of the bench targets. update.sh does survey->guards->
# build->roll->verify; guards HALT on judgment calls (mock compat, missing
# .env keys) — resolve, then re-run with the suggested flag.
field-dry:     ; @FIELD_SSH=$${FIELD_SSH:-orin-tail} ops/field/update.sh --dry-run
field-update:  ; @FIELD_SSH=$${FIELD_SSH:-orin-tail} ops/field/update.sh $(FLAGS)
field-status:  ; @ssh -o BatchMode=yes $${FIELD_SSH:-orin-tail} 'cd ~/bic-v2 && ./deploy.sh status'
down:          ; @$(ENV)/down.sh
restart-lab:    ; @$(ENV)/restart.sh lab
restart-BE:     ; @$(ENV)/restart.sh BE
restart-portal: ; @$(ENV)/restart.sh portal
restart-mock:   ; @$(ENV)/restart.sh mock
restart-chem:   ; @$(ENV)/restart.sh chem
