"""Reads state education outcomes from the NAEP Data Service.

NAEP — the National Assessment of Educational Progress — is the only test
given the same way in every state, which is what makes it usable here. State
proficiency tests are set by the states themselves, so comparing them across
states compares the exams as much as the students.

The service is public and needs no key. It is also slow and occasionally times
out on large requests, so responses are cached to disk and the fetch is split
by subject and grade rather than asked for all at once.

Docs: https://www.nationsreportcard.gov/api_documentation.aspx
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

BASE_URL = "https://www.nationsreportcard.gov/Dataservice/GetAdhocData.aspx"

# The scale each subject is reported on. NAEP scores are not percentages: maths
# runs roughly 250-300 at grade 8, reading roughly 200-230 at grade 4, and the
# two are not comparable to each other. Normalising them is a decision the
# index has to make explicitly rather than by accident.
SUBSCALES = {"mathematics": "MRPCM", "reading": "RRPCM"}

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

# NAEP runs every two years, so there is no annual series to plot. 2024 is the
# most recent administration for maths and reading.
LATEST_YEAR = 2024


def cache_path(root: Path, subject: str, grade: int, year: int) -> Path:
    return root / "data" / "raw" / f"naep_{subject}_g{grade}_{year}.json"


def fetch_subject(
    subject: str,
    grade: int,
    year: int = LATEST_YEAR,
    *,
    root: Path,
    use_cache: bool = True,
    session: requests.Session | None = None,
) -> dict[str, float]:
    """Returns {state code: mean scale score} for one subject and grade.

    Cached to disk because the service is slow and the data only changes every
    two years — re-fetching on every run would be rude to a public service and
    would make the build non-deterministic for no benefit.
    """
    if subject not in SUBSCALES:
        raise ValueError(f"Unknown subject {subject!r}; expected one of {sorted(SUBSCALES)}")

    path = cache_path(root, subject, grade, year)

    if use_cache and path.exists():
        return json.loads(path.read_text())

    params = {
        "type": "data",
        "subject": subject,
        "grade": grade,
        "subscale": SUBSCALES[subject],
        "variable": "TOTAL",
        "jurisdiction": ",".join(STATES),
        "stattype": "MN:MN",
        "Year": year,
    }

    client = session or requests
    response = client.get(BASE_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    if payload.get("status") != 200:
        raise RuntimeError(f"NAEP returned status {payload.get('status')} for {subject} g{grade}")

    scores: dict[str, float] = {}

    for row in payload.get("result", []):
        state = row.get("jurisdiction")
        value = row.get("value")

        # A state can be absent or flagged rather than scored. Recording it as
        # missing is the honest outcome; substituting a number here would put
        # an invented figure into the index with no way to tell later.
        if state in STATES and isinstance(value, (int, float)):
            scores[state] = round(float(value), 2)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scores, indent=2, sort_keys=True))

    return scores


def fetch_all(
    *,
    root: Path,
    year: int = LATEST_YEAR,
    use_cache: bool = True,
    pause: float = 1.0,
) -> dict[str, dict[str, float]]:
    """Fetches the four series the index uses, keyed 'subject_gradeN'."""
    series: dict[str, dict[str, float]] = {}

    for subject in ("mathematics", "reading"):
        for grade in (4, 8):
            key = f"{subject}_grade{grade}"
            cached = cache_path(root, subject, grade, year).exists()

            series[key] = fetch_subject(
                subject, grade, year, root=root, use_cache=use_cache
            )

            # Only pause when a call actually went out.
            if not cached and pause:
                time.sleep(pause)

    return series
