# Claude Code Handoff Brief: `fhir-synthea-lab`

## Purpose

Build the complete `fhir-synthea-lab` repository from scratch. This is a
reproducible local FHIR R4 development environment seeded with Synthea
synthetic patient data. It is the data foundation for a broader clinical AI
portfolio — the clinical state layer, patient timeline, and discharge
co-pilot all depend on it.

**GitHub repo:** https://github.com/Hefrock/fhir-synthea-lab

---

## What to build

Deliver a working repo that passes this end-to-end test:

```
git clone https://github.com/Hefrock/fhir-synthea-lab
cd fhir-synthea-lab
make up        # starts HAPI FHIR container
make generate  # generates Synthea patients with pinned seed
make load      # POSTs all bundles to HAPI
make verify    # runs verify.py — must exit 0
```

Everything else (CI badge, PATIENTS.md, README) supports that core flow.

---

## Architecture decisions (already made — do not change)

| Decision | Choice | Reason |
|---|---|---|
| Container count | Single container | Test/demo environment — simplicity over scalability |
| Database | H2 file persistence (not Postgres) | Persists across restarts, no second service needed |
| HAPI version | `hapiproject/hapi:v7.2.0` | Pinned — not `latest` |
| Synthea version | `v3.3.0` | Pinned — not `latest` |
| Synthea seed | `42` | Deterministic — same cohort every clone |
| Population | 50 patients | Rich enough for demo, fast to load |
| State | `Massachusetts` | Synthea default, realistic US clinical data |
| Language | Python for scripts, bash for runners | Matches `fhir-mcp-server` conventions |

---

## Repo structure to create

```
fhir-synthea-lab/
├── docker-compose.yml          ← single HAPI container, H2 volume
├── .env.example                ← documented env vars, no secrets
├── Makefile                    ← up, down, generate, load, verify, clean
├── README.md                   ← setup in 5 commands + architecture diagram
├── PATIENTS.md                 ← curated table of interesting patients (filled after load)
├── HANDOFF_BRIEF.md            ← this file (commit it for reference)
├── synthea/
│   ├── generate.sh             ← wraps Synthea CLI with pinned args
│   └── synthea.properties      ← pinned config (seed, output format, R4)
├── scripts/
│   ├── load.sh                 ← POSTs each bundle, progress output, error handling
│   ├── verify.py               ← fidelity + reproducibility checks, exits 0 or 1
│   └── find_interesting_patients.py  ← surfaces patients with most longitudinal depth
└── .github/
    └── workflows/
        └── validate.yml        ← spins up stack, loads, runs verify
```

---

## File specifications

### `docker-compose.yml`

Single service. H2 data persisted to a named volume so Synthea loads only
once. Expose port 8080.

```yaml
services:
  hapi:
    image: hapiproject/hapi:v7.2.0
    ports:
      - "8080:8080"
    volumes:
      - hapi-data:/data/hapi
    environment:
      hapi.fhir.default_encoding: json
      hapi.fhir.fhir_version: R4
      spring.datasource.url: jdbc:h2:file:/data/hapi/h2db;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE
      spring.datasource.driverClassName: org.h2.Driver
      spring.datasource.username: sa
      spring.datasource.password: ""
      spring.jpa.properties.hibernate.dialect: org.hibernate.dialect.H2Dialect

volumes:
  hapi-data:
```

### `.env.example`

```bash
# FHIR server base URL (default for local development)
FHIR_BASE_URL=http://localhost:8080/fhir

# Synthea generation settings
SYNTHEA_SEED=42
SYNTHEA_POPULATION=50
SYNTHEA_STATE=Massachusetts

# Paths
SYNTHEA_OUTPUT_DIR=./synthea/output
```

### `Makefile`

Targets:

- `make up` — `docker compose up -d`, then poll `http://localhost:8080/fhir/metadata` until HAPI is ready (retry loop, max 60s, clear error if timeout)
- `make down` — `docker compose down`
- `make generate` — runs `synthea/generate.sh`
- `make load` — runs `scripts/load.sh`
- `make verify` — runs `python scripts/verify.py`
- `make find-patients` — runs `python scripts/find_interesting_patients.py`
- `make clean` — `docker compose down -v` (destroys volume — requires confirmation prompt)
- `make all` — `up generate load verify` in sequence

### `synthea/generate.sh`

Downloads Synthea `v3.3.0` JAR if not already present (to `synthea/synthea-with-dependencies.jar`). Runs with:

```bash
java -jar synthea/synthea-with-dependencies.jar \
  -s 42 \
  -p 50 \
  -c synthea/synthea.properties \
  Massachusetts
```

Output goes to `synthea/output/fhir/`. Do not commit generated bundles —
add `synthea/output/` to `.gitignore`.

### `synthea/synthea.properties`

```properties
# Pinned configuration for reproducibility
exporter.fhir.export = true
exporter.fhir.version = R4
exporter.years_of_history = 10
exporter.baseDirectory = ./synthea/output
generate.only_alive_patients = false
generate.append_numbers_to_person_names = false
```

Setting `years_of_history = 10` ensures longitudinal depth for the
clinical state layer. `only_alive_patients = false` keeps deceased patients
— their histories are clinically useful for the timeline demo.

### `scripts/load.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

FHIR_BASE=${FHIR_BASE_URL:-http://localhost:8080/fhir}
BUNDLE_DIR=${SYNTHEA_OUTPUT_DIR:-./synthea/output/fhir}

bundles=$(find "$BUNDLE_DIR" -name "*.json" | sort)
total=$(echo "$bundles" | wc -l | tr -d ' ')
count=0
errors=0

echo "Loading $total bundles into $FHIR_BASE"

for bundle in $bundles; do
  count=$((count + 1))
  filename=$(basename "$bundle")
  
  http_code=$(curl -s -o /tmp/fhir_response.json -w "%{http_code}" \
    -X POST "$FHIR_BASE" \
    -H "Content-Type: application/fhir+json" \
    -d @"$bundle")
  
  if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo "[$count/$total] ✓ $filename"
  else
    echo "[$count/$total] ✗ $filename (HTTP $http_code)"
    errors=$((errors + 1))
  fi
done

echo ""
echo "Done. $((total - errors))/$total bundles loaded successfully."
[ "$errors" -eq 0 ] || exit 1
```

### `scripts/verify.py`

Checks fidelity and reproducibility. Exits 0 if all checks pass, 1 if any
fail. Print a clear summary — this runs in CI.

**Checks to implement:**

```python
FHIR_BASE = os.getenv("FHIR_BASE_URL", "http://localhost:8080/fhir")

# --- Volume checks ---
# 1. Patient count: must be >= 40 (allow for a few failed loads)
# 2. Every patient must have >= 1 Condition
# 3. Every patient must have >= 1 MedicationRequest
# 4. Every patient must have >= 1 Observation

# --- Longitudinal depth checks ---
# 5. At least one patient must have >= 20 Observations
# 6. At least one patient must have Observations spanning >= 5 years
# 7. At least one Condition must have a clinicalStatus of "active"
#    and an onsetDateTime at least 2 years ago

# --- Coding integrity checks ---
# 8. Sample 10 Observations — all must have a .code.coding[].system
#    of "http://loinc.org"
# 9. Sample 10 Conditions — all must have a .code.coding[].system
#    of "http://snomed.info/sct"
# 10. Sample 10 MedicationRequests — all must have a medication
#    coding present (RxNorm or NDC)

# --- Reproducibility check ---
# 11. Record patient count and a sorted list of patient family names
#     to a file: scripts/.verify_baseline.json
#     On subsequent runs, compare against baseline and fail if they differ.
#     Print "Baseline created" on first run, "Baseline matched" on subsequent.
```

Output format example:
```
fhir-synthea-lab verify
========================
[PASS] Patient count: 50
[PASS] All patients have Conditions
[PASS] All patients have MedicationRequests
[PASS] All patients have Observations
[PASS] Longitudinal depth: patient abc123 has 147 Observations
[PASS] Date range: patient abc123 spans 12.3 years
[PASS] Active chronic condition found with 8.1 year history
[PASS] LOINC codes present on sampled Observations
[PASS] SNOMED codes present on sampled Conditions
[PASS] Medication codings present on sampled MedicationRequests
[PASS] Reproducibility baseline matched

11/11 checks passed.
```

### `scripts/find_interesting_patients.py`

Queries the loaded HAPI instance and prints a ranked table of patients by
longitudinal richness. Output feeds `PATIENTS.md`.

Rank patients by a composite score:
- Observation count (most weight)
- Date span of records in years
- Number of distinct active Conditions
- Number of distinct MedicationRequest drug classes

Print top 10 as a table:

```
Rank  Patient ID   Name              Obs   Span(yrs)  Conditions  Meds
1     abc123       Smith, John       147   12.3       5           4
2     def456       Jones, Mary       134   10.8       3           3
...
```

Also flag any patient who has:
- A Condition with `diabetes` in the display text AND a LOINC A1C
  observation (8867-4 is HbA1c — actually the LOINC for A1C is 4548-4)
- A MedicationRequest for metformin AND insulin (escalation arc)
- A Condition onset > 5 years ago with active status

These are the "demo patients" — call them out explicitly:

```
Demo candidates (clinical narrative depth):
  - abc123: T2DM with medication escalation (metformin → insulin), 8yr history
```

### `PATIENTS.md`

Fill this after running `make find-patients`. Template:

```markdown
# Patient Cohort

Generated with Synthea v3.3.0, seed 42, 50 patients, Massachusetts.
Run `make find-patients` to reproduce this table.

## Top patients by longitudinal depth

| Rank | Patient ID | Obs | Span | Conditions | Clinical narrative |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... |

## Demo patients

Patients with compelling clinical arcs suitable for timeline and
discharge co-pilot demos.

| Patient ID | Narrative | Why useful |
|---|---|---|
| ... | T2DM with metformin → insulin escalation | Shows medication state transitions |

## How to query a patient

Point your MCP server at this stack:
\`\`\`bash
FHIR_BASE_URL=http://localhost:8080/fhir fhir-mcp-server
\`\`\`
Then ask: "Give me a full summary of patient {id}"
```

### `README.md`

```markdown
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

\`\`\`bash
git clone https://github.com/Hefrock/fhir-synthea-lab
cd fhir-synthea-lab
make up        # starts HAPI FHIR at http://localhost:8080
make generate  # generates 50 Synthea patients (pinned seed 42)
make load      # loads bundles into HAPI (~2 min)
make verify    # confirms data fidelity and reproducibility
\`\`\`

## Architecture

\`\`\`
synthea/generate.sh
    → synthea/output/fhir/*.json   (FHIR R4 transaction bundles)
    → scripts/load.sh              (POST each bundle to HAPI)
    → HAPI FHIR (hapiproject/hapi:v7.2.0)
        → H2 file database         (persisted via Docker volume)
        → exposed at :8080/fhir
\`\`\`

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

\`\`\`bash
FHIR_BASE_URL=http://localhost:8080/fhir fhir-mcp-server
\`\`\`

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
| `make all` | up → generate → load → verify |
| `make clean` | Destroy container and volume (destructive) |

## Not for clinical use

All data is synthetic. This repo is for development and portfolio
demonstration only.
\`\`\`

### `.github/workflows/validate.yml`

```yaml
name: Validate

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Python deps
        run: pip install requests

      - name: Set up Java (for Synthea)
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"

      - name: Start HAPI FHIR
        run: docker compose up -d

      - name: Wait for HAPI readiness
        run: |
          for i in $(seq 1 30); do
            curl -sf http://localhost:8080/fhir/metadata > /dev/null && echo "HAPI ready" && exit 0
            echo "Waiting... ($i/30)"
            sleep 5
          done
          echo "HAPI did not start in time" && exit 1

      - name: Generate Synthea patients
        run: make generate

      - name: Load bundles
        run: make load

      - name: Verify fidelity and reproducibility
        run: make verify
        env:
          FHIR_BASE_URL: http://localhost:8080/fhir
```

---

## .gitignore additions

```
synthea/output/
synthea/synthea-with-dependencies.jar
scripts/.verify_baseline.json
.env
__pycache__/
*.pyc
```

Note: `.verify_baseline.json` is gitignored because it contains patient IDs
that are environment-specific. The reproducibility check creates it on
first run and compares on subsequent runs — it is a local artifact, not a
committed one.

---

## Definition of done

Claude Code should confirm each of these before finishing:

- [ ] `make all` completes without errors on a fresh clone
- [ ] `make verify` exits 0 with 11/11 checks passing
- [ ] `make find-patients` prints a ranked table with demo patient callouts
- [ ] GitHub Actions `validate.yml` workflow passes on push
- [ ] README renders correctly on GitHub (check the architecture diagram)
- [ ] No secrets, no PHI, no generated bundles committed
- [ ] All pinned versions (HAPI v7.2.0, Synthea v3.3.0) used — not `latest`

---

## Context: where this fits

```
fhir-synthea-lab          ← YOU ARE BUILDING THIS
        ↓
fhir-mcp-server           ← done (github.com/Hefrock/fhir-mcp-server)
        ↓
clinical-state-layer      ← next (not started)
        ↓
patient-timeline          ← next (not started)
        ↓
discharge-copilot         ← capstone (not started)
```

The `FHIR_BASE_URL` env var on `fhir-mcp-server` is the only connection
point — point it at `http://localhost:8080/fhir` and the MCP server works
against this stack with zero code changes. That is the architecture to
preserve.
