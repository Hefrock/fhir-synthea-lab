#!/usr/bin/env python3
"""Fidelity and reproducibility checks for the fhir-synthea-lab stack."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

FHIR_BASE = os.getenv("FHIR_BASE_URL", "http://localhost:8080/fhir")
BASELINE_PATH = Path(__file__).parent / ".verify_baseline.json"

MIN_PATIENT_COUNT = 40
MIN_OBSERVATIONS_FOR_DEPTH = 20
MIN_SPAN_YEARS = 5
MIN_CONDITION_AGE_YEARS = 2
SAMPLE_SIZE = 10

results = []


def check(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    msg = f"[{status}] {label}" + (f": {detail}" if detail else "")
    print(msg)
    results.append(passed)
    return passed


def fhir_get(path, params=None):
    resp = requests.get(f"{FHIR_BASE}/{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_all_pages(path, params):
    entries = []
    bundle = fhir_get(path, params)
    while True:
        entries.extend(bundle.get("entry", []))
        next_link = next(
            (link["url"] for link in bundle.get("link", []) if link.get("rel") == "next"),
            None,
        )
        if not next_link:
            break
        resp = requests.get(next_link, timeout=30)
        resp.raise_for_status()
        bundle = resp.json()
    return entries


def parse_fhir_datetime(value):
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def main():
    print("fhir-synthea-lab verify")
    print("========================")

    # 1. Patient count
    patient_bundle = fhir_get("Patient", {"_summary": "count"})
    patient_count = patient_bundle.get("total", 0)
    check("Patient count", patient_count >= MIN_PATIENT_COUNT, f"{patient_count}")

    patients = fetch_all_pages("Patient", {"_count": 50, "_elements": "id,name"})
    patient_ids = [e["resource"]["id"] for e in patients]

    # 2-4. Every patient must have >=1 Condition / MedicationRequest / Observation
    missing_conditions = []
    missing_meds = []
    missing_obs = []
    obs_counts = {}
    obs_date_ranges = {}

    for pid in patient_ids:
        cond_count = fhir_get(
            "Condition", {"patient": pid, "_summary": "count"}
        ).get("total", 0)
        if cond_count < 1:
            missing_conditions.append(pid)

        med_count = fhir_get(
            "MedicationRequest", {"patient": pid, "_summary": "count"}
        ).get("total", 0)
        if med_count < 1:
            missing_meds.append(pid)

        obs_bundle = fhir_get(
            "Observation",
            {"patient": pid, "_summary": "count"},
        )
        obs_count = obs_bundle.get("total", 0)
        obs_counts[pid] = obs_count
        if obs_count < 1:
            missing_obs.append(pid)

    check(
        "All patients have Conditions",
        not missing_conditions,
        f"{len(missing_conditions)} missing" if missing_conditions else "",
    )
    check(
        "All patients have MedicationRequests",
        not missing_meds,
        f"{len(missing_meds)} missing" if missing_meds else "",
    )
    check(
        "All patients have Observations",
        not missing_obs,
        f"{len(missing_obs)} missing" if missing_obs else "",
    )

    # 5. At least one patient with >= 20 Observations
    richest_pid = max(obs_counts, key=lambda k: obs_counts[k]) if obs_counts else None
    richest_count = obs_counts.get(richest_pid, 0)
    check(
        "Longitudinal depth",
        richest_count >= MIN_OBSERVATIONS_FOR_DEPTH,
        f"patient {richest_pid} has {richest_count} Observations",
    )

    # 6. At least one patient with Observations spanning >= 5 years
    best_span = 0.0
    best_span_pid = None
    for pid in patient_ids:
        entries = fetch_all_pages(
            "Observation",
            {"patient": pid, "_count": 200, "_elements": "effectiveDateTime,effectivePeriod"},
        )
        dates = []
        for e in entries:
            res = e["resource"]
            dt = res.get("effectiveDateTime") or (res.get("effectivePeriod") or {}).get("start")
            parsed = parse_fhir_datetime(dt)
            if parsed:
                dates.append(parsed)
        if len(dates) >= 2:
            span_years = (max(dates) - min(dates)).days / 365.25
            if span_years > best_span:
                best_span = span_years
                best_span_pid = pid

    check(
        "Date range",
        best_span >= MIN_SPAN_YEARS,
        f"patient {best_span_pid} spans {best_span:.1f} years",
    )

    # 7. At least one active Condition with onset >= 2 years ago
    now = datetime.now(timezone.utc)
    found_active_old_condition = False
    found_detail = ""
    for pid in patient_ids:
        entries = fetch_all_pages(
            "Condition",
            {"patient": pid, "clinical-status": "active", "_count": 100},
        )
        for e in entries:
            res = e["resource"]
            onset = parse_fhir_datetime(res.get("onsetDateTime"))
            if onset:
                age_years = (now - onset).days / 365.25
                if age_years >= MIN_CONDITION_AGE_YEARS:
                    found_active_old_condition = True
                    found_detail = f"{age_years:.1f} year history"
                    break
        if found_active_old_condition:
            break

    check(
        "Active chronic condition found",
        found_active_old_condition,
        found_detail,
    )

    # 8. Sample 10 Observations -> LOINC coding
    obs_sample = fetch_all_pages("Observation", {"_count": SAMPLE_SIZE})
    loinc_ok = bool(obs_sample) and all(
        any(
            coding.get("system") == "http://loinc.org"
            for coding in e["resource"].get("code", {}).get("coding", [])
        )
        for e in obs_sample
    )
    check("LOINC codes present on sampled Observations", loinc_ok)

    # 9. Sample 10 Conditions -> SNOMED coding
    cond_sample = fetch_all_pages("Condition", {"_count": SAMPLE_SIZE})
    snomed_ok = bool(cond_sample) and all(
        any(
            coding.get("system") == "http://snomed.info/sct"
            for coding in e["resource"].get("code", {}).get("coding", [])
        )
        for e in cond_sample
    )
    check("SNOMED codes present on sampled Conditions", snomed_ok)

    # 10. Sample 10 MedicationRequests -> medication coding present
    med_sample = fetch_all_pages("MedicationRequest", {"_count": SAMPLE_SIZE})

    def has_med_coding(res):
        med_concept = res.get("medicationCodeableConcept", {})
        return bool(med_concept.get("coding"))

    med_ok = bool(med_sample) and all(has_med_coding(e["resource"]) for e in med_sample)
    check("Medication codings present on sampled MedicationRequests", med_ok)

    # 11. Reproducibility check
    family_names = sorted(
        e["resource"].get("name", [{}])[0].get("family", "")
        for e in patients
    )
    current_state = {"patient_count": patient_count, "family_names": family_names}

    if BASELINE_PATH.exists():
        baseline = json.loads(BASELINE_PATH.read_text())
        matched = baseline == current_state
        check("Reproducibility baseline matched", matched)
        if not matched:
            print(
                f"  baseline: {baseline}\n  current:  {current_state}",
                file=sys.stderr,
            )
    else:
        BASELINE_PATH.write_text(json.dumps(current_state, indent=2))
        check("Reproducibility baseline created", True, "Baseline created")

    print()
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"{passed}/{total} checks passed.")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
