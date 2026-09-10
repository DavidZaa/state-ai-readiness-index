"""Per-pupil school spending, from the Urban Institute's Education Data API.

The API wraps the Department of Education's Common Core of Data and is public,
keyless, and — usefully — will aggregate for us, so two requests give totals for
every state instead of thirteen thousand district rows.

Two things about this measure that the interface has to say out loud.

**It lags.** School finance is collected slowly and the newest year available is
2020, four years behind the NAEP figures. Putting a 2020 number next to a 2024
one is a compromise, not a detail.

**It is the confounder.** Everything else in this index tends to move with money,
which is exactly the objection the site makes to its own ranking. Including
spending does not resolve that — it makes it visible, and it puts the project's
own prediction to the test: a measure correlated with the others should make the
ranking *more* stable and shrink the headline finding.

Docs: https://educationdata.urban.org/documentation/
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

BASE = "https://educationdata.urban.org/api/v1/school-districts/ccd"

# Finance stops here even though enrollment runs later; using a newer
# enrollment year would divide spending by a roll it never paid for.
FINANCE_YEAR = 2020

SOURCE = "Common Core of Data, via the Urban Institute Education Data API"
SOURCE_URL = "https://educationdata.urban.org/documentation/"

# FIPS codes are how this API identifies states. DC and the territories are
# dropped: the index covers the 50 states, and quietly averaging a territory
# into a state ranking would be its own small dishonesty.
FIPS_TO_STATE = {
    1: "AL", 2: "AK", 4: "AZ", 5: "AR", 6: "CA", 8: "CO", 9: "CT", 10: "DE",
    12: "FL", 13: "GA", 15: "HI", 16: "ID", 17: "IL", 18: "IN", 19: "IA",
    20: "KS", 21: "KY", 22: "LA", 23: "ME", 24: "MD", 25: "MA", 26: "MI",
    27: "MN", 28: "MS", 29: "MO", 30: "MT", 31: "NE", 32: "NV", 33: "NH",
    34: "NJ", 35: "NM", 36: "NY", 37: "NC", 38: "ND", 39: "OH", 40: "OK",
    41: "OR", 42: "PA", 44: "RI", 45: "SC", 46: "SD", 47: "TN", 48: "TX",
    49: "UT", 50: "VT", 51: "VA", 53: "WA", 54: "WV", 55: "WI", 56: "WY",
}


def _summary(endpoint: str, var: str, year: int, **extra) -> dict[int, float]:
    params = {"var": var, "stat": "sum", "by": "fips", "year": year, **extra}
    response = requests.get(f"{BASE}/{endpoint}/summaries", params=params, timeout=60)
    response.raise_for_status()

    return {
        row["fips"]: row[var]
        for row in response.json().get("results", [])
        if isinstance(row.get(var), (int, float)) and row[var] > 0
    }


def fetch_per_pupil(*, year: int = FINANCE_YEAR) -> dict[str, float]:
    """Returns {state code: dollars spent per enrolled pupil}."""
    spending = _summary("finance", "exp_total", year)
    enrolment = _summary("enrollment", "enrollment", year, grade=99)

    per_pupil: dict[str, float] = {}

    for fips, state in FIPS_TO_STATE.items():
        total = spending.get(fips)
        pupils = enrolment.get(fips)

        # A state missing either half is left out rather than estimated. The
        # index shows missing data; it does not fill it.
        if total and pupils:
            per_pupil[state] = round(total / pupils, 2)

    return per_pupil


def load(root: Path) -> dict[str, float]:
    """Reads the committed snapshot, falling back to a live fetch."""
    path = root / "data" / "processed" / "spending_per_pupil.json"

    if path.exists():
        payload = json.loads(path.read_text())

        if payload.get("values"):
            return {state: float(value) for state, value in payload["values"].items()}

    return fetch_per_pupil()
