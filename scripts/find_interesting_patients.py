#!/usr/bin/env python3
"""Rank loaded patients by longitudinal clinical depth and flag demo candidates."""

import os
from datetime import datetime, timezone

import requests

FHIR_BASE = os.getenv("FHIR_BASE_URL", "http://localhost:8080/fhir")

A1C_LOINC = "4548-4"
DIABETES_TERMS = ("diabetes",)
METFORMIN_TERM = "metformin"
INSULIN_TERM = "insulin"
CHRONIC_ONSET_YEARS = 5


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
            (link["url"] for link in bundle.get("link", []) if link["rel"] == "next"),
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


def patient_display_name(resource):
    names = resource.get("name", [])
    if not names:
        return resource.get("id", "unknown")
    name = names[0]
    family = name.get("family", "")
    given = " ".join(name.get("given", []))
    return f"{family}, {given}".strip(", ")


def drug_class(med_request):
    concept = med_request.get("medicationCodeableConcept", {})
    text = (concept.get("text") or "").lower()
    for coding in concept.get("coding", []):
        text += " " + (coding.get("display") or "").lower()
    return text


def main():
    now = datetime.now(timezone.utc)
    patients = fetch_all_pages("Patient", {"_count": 100})

    rows = []
    demo_candidates = []

    for entry in patients:
        patient = entry["resource"]
        pid = patient["id"]
        name = patient_display_name(patient)

        obs_entries = fetch_all_pages(
            "Observation",
            {"patient": pid, "_count": 200, "_elements": "effectiveDateTime,effectivePeriod,code"},
        )
        obs_count = len(obs_entries)

        dates = []
        has_a1c = False
        for e in obs_entries:
            res = e["resource"]
            dt = res.get("effectiveDateTime") or (res.get("effectivePeriod") or {}).get("start")
            parsed = parse_fhir_datetime(dt)
            if parsed:
                dates.append(parsed)
            for coding in res.get("code", {}).get("coding", []):
                if coding.get("system") == "http://loinc.org" and coding.get("code") == A1C_LOINC:
                    has_a1c = True

        span_years = (max(dates) - min(dates)).days / 365.25 if len(dates) >= 2 else 0.0

        cond_entries = fetch_all_pages(
            "Condition",
            {"patient": pid, "clinical-status": "active", "_count": 100},
        )
        active_conditions = [e["resource"] for e in cond_entries]
        condition_count = len(active_conditions)

        has_diabetes = any(
            term in (cond.get("code", {}).get("text") or "").lower()
            for cond in active_conditions
            for term in DIABETES_TERMS
        )

        has_old_chronic = False
        for cond in active_conditions:
            onset = parse_fhir_datetime(cond.get("onsetDateTime"))
            if onset and (now - onset).days / 365.25 > CHRONIC_ONSET_YEARS:
                has_old_chronic = True

        med_entries = fetch_all_pages("MedicationRequest", {"patient": pid, "_count": 100})
        med_classes = {drug_class(e["resource"]) for e in med_entries}
        med_class_count = len(med_classes)

        has_metformin = any(METFORMIN_TERM in cls for cls in med_classes)
        has_insulin = any(INSULIN_TERM in cls for cls in med_classes)

        score = obs_count * 3 + span_years * 5 + condition_count * 2 + med_class_count

        rows.append(
            {
                "pid": pid,
                "name": name,
                "obs": obs_count,
                "span": span_years,
                "conditions": condition_count,
                "meds": med_class_count,
                "score": score,
            }
        )

        narrative = []
        if has_diabetes and has_a1c:
            narrative.append("T2DM with A1C tracking")
        if has_metformin and has_insulin:
            narrative.append("medication escalation (metformin -> insulin)")
        if has_old_chronic:
            narrative.append(f">{CHRONIC_ONSET_YEARS}yr active chronic condition")

        if narrative:
            demo_candidates.append({"pid": pid, "name": name, "narrative": "; ".join(narrative)})

    rows.sort(key=lambda r: r["score"], reverse=True)

    print(f"{'Rank':<5} {'Patient ID':<13} {'Name':<20} {'Obs':<6} {'Span(yrs)':<10} {'Conditions':<11} {'Meds'}")
    for i, row in enumerate(rows[:10], start=1):
        print(
            f"{i:<5} {row['pid']:<13} {row['name']:<20} {row['obs']:<6} "
            f"{row['span']:<10.1f} {row['conditions']:<11} {row['meds']}"
        )

    print()
    print("Demo candidates (clinical narrative depth):")
    if demo_candidates:
        for c in demo_candidates:
            print(f"  - {c['pid']}: {c['narrative']}")
    else:
        print("  (none found)")


if __name__ == "__main__":
    main()
