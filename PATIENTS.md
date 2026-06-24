# Patient Cohort

Generated with Synthea v3.3.0, seed 42, 50 patients, Massachusetts.
Run `make find-patients` to reproduce this table.

## Top patients by longitudinal depth

| Rank | Patient ID | Obs | Span | Conditions | Clinical narrative |
|---|---|---|---|---|---|
| - | _run `make find-patients` after `make load` to populate this table_ | | | | |

## Demo patients

Patients with compelling clinical arcs suitable for timeline and
discharge co-pilot demos.

| Patient ID | Narrative | Why useful |
|---|---|---|
| _TBD_ | T2DM with metformin -> insulin escalation | Shows medication state transitions |

## How to query a patient

Point your MCP server at this stack:
```bash
FHIR_BASE_URL=http://localhost:8080/fhir fhir-mcp-server
```
Then ask: "Give me a full summary of patient {id}"
