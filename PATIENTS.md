# Patient Cohort

Generated with Synthea v3.3.0, seed 42, 50 patients, Massachusetts.
Run `make find-patients` to reproduce this table against a live HAPI load.

> **Note on methodology:** this table was computed by applying
> `find_interesting_patients.py`'s scoring logic directly to the locally
> generated Synthea bundles (sandbox network policy blocked the
> `hapiproject/hapi` image pull needed for a live `make load` run). The
> seed is pinned, so patient IDs and stats below should match a real
> `make find-patients` run after `make load`. Re-run `make find-patients`
> against a live load to confirm and refresh this table.

## Top patients by longitudinal depth

| Rank | Patient ID | Obs | Span (yrs) | Conditions | Clinical narrative |
|---|---|---|---|---|---|
| 1 | `9c6736d8-361a-4a4a-ad13-6fe3f4d5a82a` | 4314 | 9.7 | 24 | Blaine Joseph Kiehn — densest record in cohort |
| 2 | `6c336b6f-4647-45ef-a6a6-3441b20657e2` | 4151 | 9.6 | 21 | Jeniffer Ebert — T2DM with A1C tracking, >5yr chronic condition |
| 3 | `347ceebf-0248-5a56-14f3-e1e8e8ffb73c` | 4000 | 9.7 | 29 | Lecia Lizabeth Abbott — T2DM with A1C tracking, most distinct conditions |
| 4 | `c63fbc4c-0f4f-70ad-e5b3-0c754949d186` | 3795 | 9.9 | 14 | Elvin Rupert Ullrich — widest date span in cohort |
| 5 | `38cc48b8-cb44-1e20-32e8-5b7e5d4bae20` | 2447 | 8.8 | 15 | Cleotilde Kali Weissnat |
| 6 | `ad842386-d06c-5bb6-f908-71452cff8b2f` | 511 | 9.1 | 21 | Eldon Cyril Durgan |
| 7 | `cd38af39-23f7-92a3-1983-ea0af5e7e011` | 435 | 9.1 | 12 | Joesph Leland Labadie — T2DM with A1C tracking |
| 8 | `2e23caa4-d831-1f47-c522-0518bab7bd3d` | 411 | 9.3 | 20 | Mariano Joaquín Tamez |
| 9 | `0e7809bd-be4e-ed66-9589-9253b729e37b` | 415 | 8.1 | 13 | Krysten Rickie Douglas |
| 10 | `5c4ba9ad-1fef-b11e-3c18-3fff986b3890` | 407 | 9.1 | 12 | Osvaldo Schuppe |

## Demo patients

Patients with compelling clinical arcs suitable for timeline and
discharge co-pilot demos. 42 patients in the cohort have an active
condition with onset more than 5 years ago — a handful of the most
clinically interesting are listed below.

| Patient ID | Narrative | Why useful |
|---|---|---|
| `347ceebf-0248-5a56-14f3-e1e8e8ffb73c` | T2DM with A1C tracking, 29 active conditions, 9.7yr history | Richest single record for a multi-problem timeline demo |
| `6c336b6f-4647-45ef-a6a6-3441b20657e2` | T2DM with A1C tracking, 9.6yr history | Strong diabetes-management narrative, second-densest record |
| `9e9f4867-2364-5bcb-ccbb-dca10f2579cb` | Vina Breitenberg — T2DM with A1C tracking, >5yr chronic condition | Good mid-volume diabetes case |
| `196b6069-9bdd-a3fb-20ce-47414b6e8cdd` | Latonya Jami King — T2DM with A1C tracking, >5yr chronic condition | Good mid-volume diabetes case |
| `cd38af39-23f7-92a3-1983-ea0af5e7e011` | Joesph Leland Labadie — T2DM with A1C tracking | Lower-volume diabetes case, useful for contrast |

**Caveat:** the brief's suggested "metformin → insulin escalation" arc
does **not** occur anywhere in this seed-42 cohort of 50 — no patient
has both a metformin and an insulin `MedicationRequest`. If that specific
narrative is needed for a demo, it would require either a larger
population size or hand-picking/augmenting a patient; it's not naturally
present at this seed/population.

## How to query a patient

Point your MCP server at this stack:
```bash
FHIR_BASE_URL=http://localhost:8080/fhir fhir-mcp-server
```
Then ask: "Give me a full summary of patient {id}"
