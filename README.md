# fhir-synthea-lab

Reproducible local FHIR R4 environment seeded with Synthea synthetic
patient data. Single-container HAPI FHIR stack with H2 persistence,
pinned data generation, and verification scripts for developing and
demoing clinical AI applications.

Part of a broader clinical AI portfolio:
- Data layer: this repo
- AI access layer: [fhir-mcp-server](https://github.com/Hefrock/fhir-mcp-server)
- Clinical intelligence: clinical-state-layer (in progress)

## Quickstart

Prerequisites: Docker, Java 11+ (for Synthea generation)

```bash
git clone https://github.com/Hefrock/fhir-synthea-lab
cd fhir-synthea-lab
make up        # starts HAPI FHIR at http://localhost:8080
make generate  # generates 50 Synthea patients (pinned seed 42)
make load      # loads bundles into HAPI (~2 min)
make verify    # confirms data fidelity and reproducibility
```

## Architecture

```
synthea/generate.sh
    -> synthea/output/fhir/*.json   (FHIR R4 transaction bundles)
    -> scripts/load.sh              (POST each bundle to HAPI)
    -> HAPI FHIR (hapiproject/hapi:v7.2.0)
        -> H2 file database         (persisted via Docker volume)
        -> exposed at :8080/fhir
```

## Pinned versions

| Component | Version |
|---|---|
| HAPI FHIR | v7.2.0 |
| Synthea | v3.3.0 |
| Seed | 42 |
| Population | 50 patients, Massachusetts |

Pinning ensures anyone who clones this repo gets an identical patient
cohort. A passing `make verify` run confirms this.

## Connecting fhir-mcp-server

```bash
FHIR_BASE_URL=http://localhost:8080/fhir fhir-mcp-server
```

See [PATIENTS.md](./PATIENTS.md) for curated demo patient IDs.

## Make targets

| Target | What it does |
|---|---|
| `make up` | Start HAPI container, wait for readiness |
| `make down` | Stop container (data persists) |
| `make generate` | Generate Synthea patients |
| `make load` | Load bundles into HAPI |
| `make verify` | Run fidelity + reproducibility checks |
| `make find-patients` | Surface top patients by longitudinal depth |
| `make all` | up -> generate -> load -> verify |
| `make clean` | Destroy container and volume (destructive) |

## Not for clinical use

All data is synthetic. This repo is for development and portfolio
demonstration only.
