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

# Default BIC_ROOT: autodetect the two known layouts (keep in sync with
# scripts/bic-env/common.sh) — nested (service repos cloned inside this repo)
# vs sibling (this repo cloned next to them). Override via env or `make X=...`.
BIC_ROOT ?= $(shell [ -d "$(CURDIR)/BIC-agent-service" ] && echo "$(CURDIR)" || echo "$(abspath $(CURDIR)/..)")
export BIC_ROOT BIC_PROFILE DRY INFRA CHEM_DIR INFRA_DIR

.DEFAULT_GOAL := help
.PHONY: help up doctor status down restart-lab restart-BE restart-portal restart-mock restart-chem \
        bootstrap bootstrap-backend bootstrap-portal bootstrap-lab bootstrap-shared

help: ## Show this help
	@echo "BIC env — one-shot local bring-up"
	@echo ""
	@echo "  make up        idempotent bring-up + self-heal (DRY=1 to preview)"
	@echo "  make doctor    read-only full checkup (each red card has a fix command)"
	@echo "  make status    one-screen service:port:status:sha"
	@echo "  make down      stop app services (INFRA=1 also stops shared infra)"
	@echo "  make restart-<svc>   lab | BE | portal | mock | chem"
	@echo ""
	@echo "  BIC_ROOT=$(BIC_ROOT)"
	@echo "  Troubleshooting appendix: ops/run-latest-2026-07-10.md"

## --- one-shot env ----------------------------------------------------------
up:            ; @$(ENV)/up.sh
doctor:        ; @$(ENV)/doctor.sh
status:        ; @$(ENV)/status.sh
down:          ; @$(ENV)/down.sh
restart-lab:    ; @$(ENV)/restart.sh lab
restart-BE:     ; @$(ENV)/restart.sh BE
restart-portal: ; @$(ENV)/restart.sh portal
restart-mock:   ; @$(ENV)/restart.sh mock
restart-chem:   ; @$(ENV)/restart.sh chem

## --- repo bootstrap (clone missing sibling repos) --------------------------
BOOTSTRAP := ./scripts/bootstrap.sh
bootstrap:          ; $(BOOTSTRAP) all
bootstrap-backend:  ; $(BOOTSTRAP) backend
bootstrap-portal:   ; $(BOOTSTRAP) portal
bootstrap-lab:      ; $(BOOTSTRAP) lab
bootstrap-shared:   ; $(BOOTSTRAP) shared
