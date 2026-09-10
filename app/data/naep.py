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


def usable(row: dict) -> bool:
    """Whether a NAEP row carries a real score.

    The service does not omit unavailable figures — it returns them with a
    sentinel value of 999 alongside `isStatDisplayable: 0` and a non-zero
    `errorFlag`. Two of the urban districts come back that way for 2024. A
    reader that only checks the value is a number will treat 999 as a score,
    rank that jurisdiction first, and never show any sign of it. So the flags
    are what decide, and the value is only trusted once they agree.
    """
    if row.get("isStatDisplayable") != 1 or row.get("errorFlag"):
        return False

    value = row.get("value")

    # 999 is the sentinel. Even flagged as displayable it is not a NAEP scale
    # score — the scales top out far below it.
    return isinstance(value, (int, float)) and 0 < float(value) < 500


def cache_path(root: Path, subject: str, grade: int, year: int, kind: str = "state") -> Path:
    suffix = "" if kind == "state" else f"_{kind}"

    return root / "data" / "raw" / f"naep_{subject}_g{grade}_{year}{suffix}.json"


def fetch_subject(
    subject: str,
    grade: int,
    year: int = LATEST_YEAR,
    *,
    root: Path,
    use_cache: bool = True,
    session: requests.Session | None = None,
    jurisdictions: list[str] | None = None,
    kind: str = "state",
) -> dict[str, float]:
    """Returns {state code: mean scale score} for one subject and grade.

    Cached to disk because the service is slow and the data only changes every
    two years — re-fetching on every run would be rude to a public service and
    would make the build non-deterministic for no benefit.
    """
    if subject not in SUBSCALES:
        raise ValueError(f"Unknown subject {subject!r}; expected one of {sorted(SUBSCALES)}")

    jurisdictions = jurisdictions or STATES
    path = cache_path(root, subject, grade, year, kind)

    if use_cache and path.exists():
        return json.loads(path.read_text())

    params = {
        "type": "data",
        "subject": subject,
        "grade": grade,
        "subscale": SUBSCALES[subject],
        "variable": "TOTAL",
        "jurisdiction": ",".join(jurisdictions),
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
        code = row.get("jurisdiction")

        if code not in jurisdictions or not usable(row):
            continue

        scores[code] = round(float(row["value"]), 2)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scores, indent=2, sort_keys=True))

    return scores


def fetch_all(
    *,
    root: Path,
    year: int = LATEST_YEAR,
    use_cache: bool = True,
    pause: float = 1.0,
    jurisdictions: list[str] | None = None,
    kind: str = "state",
) -> dict[str, dict[str, float]]:
    """Fetches the four series the index uses, keyed 'subject_gradeN'."""
    series: dict[str, dict[str, float]] = {}

    for subject in ("mathematics", "reading"):
        for grade in (4, 8):
            key = f"{subject}_grade{grade}"
            cached = cache_path(root, subject, grade, year, kind).exists()

            series[key] = fetch_subject(
                subject, grade, year, root=root, use_cache=use_cache,
                jurisdictions=jurisdictions, kind=kind,
            )

            # Only pause when a call actually went out.
            if not cached and pause:
                time.sleep(pause)

    return series


# The urban districts NAEP assesses under TUDA — Trends in Urban District
# Assessment. These take the same test as the states, in the same year, which
# is the only reason a city index is possible at all: there is no other
# achievement measure collected identically across cities.
#
# They are school districts, not cities. Several cover a whole county and are
# named accordingly, and a district's boundary is not a city's — so the page
# says "district" wherever it would be tempting to say "city".
DISTRICTS = {
    "XQ": ("Albuquerque", "NM"),
    "XA": ("Atlanta", "GA"),
    "XU": ("Austin", "TX"),
    "XM": ("Baltimore City", "MD"),
    "XB": ("Boston", "MA"),
    "XT": ("Charlotte", "NC"),
    "XC": ("Chicago", "IL"),
    "XX": ("Clark County (Las Vegas)", "NV"),
    "XV": ("Cleveland", "OH"),
    "XS": ("Dallas", "TX"),
    "XY": ("Denver", "CO"),
    "XR": ("Detroit", "MI"),
    "XW": ("District of Columbia", None),
    "XE": ("Duval County (Jacksonville)", "FL"),
    "XZ": ("Fort Worth", "TX"),
    "XF": ("Fresno", "CA"),
    "XG": ("Guilford County (Greensboro)", "NC"),
    "XO": ("Hillsborough County (Tampa)", "FL"),
    "XH": ("Houston", "TX"),
    "XJ": ("Jefferson County (Louisville)", "KY"),
    "XL": ("Los Angeles", "CA"),
    "XI": ("Miami-Dade", "FL"),
    "XK": ("Milwaukee", "WI"),
    "XN": ("New York City", "NY"),
    "XP": ("Philadelphia", "PA"),
    "XD": ("San Diego", "CA"),
    "YA": ("Shelby County (Memphis)", "TN"),
    "YB": ("Orange County (Orlando)", "FL"),
}

DISTRICT_CODES = list(DISTRICTS)
