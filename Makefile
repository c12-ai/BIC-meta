.PHONY: bootstrap bootstrap-backend bootstrap-portal bootstrap-lab bootstrap-shared

BOOTSTRAP := ./scripts/bootstrap.sh

bootstrap:
	$(BOOTSTRAP) all

bootstrap-backend:
	$(BOOTSTRAP) backend

bootstrap-portal:
	$(BOOTSTRAP) portal

bootstrap-lab:
	$(BOOTSTRAP) lab

bootstrap-shared:
	$(BOOTSTRAP) shared
