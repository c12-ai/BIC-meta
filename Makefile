# BIC one-shot environment — thin entry. All logic lives in scripts/bic-env/*.
# Coworker story: clone this repo, `make up`, done. `make doctor` explains the rest.
#
# Knobs (env or `make X=... target`):
#   BIC_ROOT=/path      where the service repos live (default: autodetected —
#                       this repo if they're nested inside it, else its parent)
#   BIC_PROFILE=minimal|full-real   (default minimal: Mind mocked + local MinIO)
#   DRY=1               up/restart: print planned actions, change nothing
#   INFRA=1             down: also stop the shared docker infra
#   CHEM_DIR=/path INFRA_DIR=/path   override auto-detection

ENV := ./scripts/bic-env

# Default BIC_ROOT resolution order: explicit env / make X=... > .bic-env
# machine pin (gitignored, see common.sh) > autodetect (nested: repos inside
# this repo; sibling: this repo cloned next to them). The pin exists because
# autodetect can land on a WRONG parent dir holding stale same-named repos
# (2026-07-10 incident: migrations ran from a stale checkout).
BIC_ROOT ?= $(shell . ./.bic-env 2>/dev/null; if [ -n "$$BIC_ROOT" ]; then echo "$$BIC_ROOT"; elif [ -d "$(CURDIR)/BIC-agent-service" ]; then echo "$(CURDIR)"; else echo "$(abspath $(CURDIR)/..)"; fi)
export BIC_ROOT BIC_PROFILE DRY INFRA CHEM_DIR INFRA_DIR

.DEFAULT_GOAL := help
.PHONY: help up pull update doctor status down restart-lab restart-BE restart-portal restart-mock restart-chem \
        mind-status mind-real mind-mock \
        bootstrap bootstrap-backend bootstrap-portal bootstrap-lab bootstrap-shared

help: ## Show this help
	@echo "BIC env — one-shot local bring-up"
	@echo ""
	@echo "  make pull      fast-forward all repos (meta/services/infra) to origin/main"
	@echo "  make update    pull + full restart on the new code (pull && up alone does NOT redeploy running services)"
	@echo "  make up        idempotent bring-up + self-heal (DRY=1 to preview)"
	@echo "  make doctor    read-only full checkup (each red card has a fix command)"
	@echo "  make status    one-screen service:port:status:sha"
	@echo "  make down      stop app services (INFRA=1 also stops shared infra)"
	@echo "  make restart-<svc>   lab | BE | portal | mock | chem"
	@echo ""
	@echo "  make mind-status     which AI engine is active: MOCK or REAL (read-only)"
	@echo "  make mind-real       switch to real Mind + orin MinIO (one sudo per boot)"
	@echo "  make mind-mock       switch back to Mind fixtures + local MinIO"
	@echo ""
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

## --- field (orin) ----------------------------------------------------------
# Field counterparts of the bench targets. update.sh does survey->guards->
# build->roll->verify; guards HALT on judgment calls (mock compat, missing
# .env keys) — resolve, then re-run with the suggested flag.
field-dry:     ; @FIELD_SSH=$${FIELD_SSH:-orin-tail} ops/field/update.sh --dry-run
field-update:  ; @FIELD_SSH=$${FIELD_SSH:-orin-tail} ops/field/update.sh $(FLAGS)
field-status:  ; @ssh -o BatchMode=yes $${FIELD_SSH:-orin-tail} 'cd ~/bic-v2 && ./deploy.sh status'
status:        ; @$(ENV)/status.sh
down:          ; @$(ENV)/down.sh
restart-lab:    ; @$(ENV)/restart.sh lab
restart-BE:     ; @$(ENV)/restart.sh BE
restart-portal: ; @$(ENV)/restart.sh portal
restart-mock:   ; @$(ENV)/restart.sh mock
restart-chem:   ; @$(ENV)/restart.sh chem

## --- Mind mode (mock vs real AI engine; see scripts/bic-env/mind.sh) -------
mind-status:   ; @$(ENV)/mind.sh status
mind-real:     ; @$(ENV)/mind.sh real
mind-mock:     ; @$(ENV)/mind.sh mock

## --- repo bootstrap (clone missing sibling repos) --------------------------
BOOTSTRAP := ./scripts/bootstrap.sh
bootstrap:          ; $(BOOTSTRAP) all
bootstrap-backend:  ; $(BOOTSTRAP) backend
bootstrap-portal:   ; $(BOOTSTRAP) portal
bootstrap-lab:      ; $(BOOTSTRAP) lab
bootstrap-shared:   ; $(BOOTSTRAP) shared
