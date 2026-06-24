.PHONY: up down generate load verify find-patients clean all

up:
	docker compose up -d
	@echo "Waiting for HAPI FHIR to become ready..."
	@for i in $$(seq 1 60); do \
		if curl -sf http://localhost:8080/fhir/metadata > /dev/null 2>&1; then \
			echo "HAPI FHIR is ready."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "ERROR: HAPI FHIR did not become ready within 60s." && exit 1

down:
	docker compose down

generate:
	bash synthea/generate.sh

load:
	bash scripts/load.sh

verify:
	python3 scripts/verify.py

find-patients:
	python3 scripts/find_interesting_patients.py

clean:
	@echo "This will destroy the HAPI container and its data volume."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || (echo "Aborted." && exit 1)
	docker compose down -v

all: up generate load verify
