"""Assembles the indicators the index runs on.

Each indicator arrives with its source, its collection year and its own
coverage. Nothing here fills a gap: a state missing from a dataset stays
missing all the way to the page, where it is shown as missing.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.data.naep import DISTRICTS, LATEST_YEAR, STATES, fetch_all
from app.index_model import Indicator

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

NAEP_SOURCE = "NAEP, National Center for Education Statistics"
NAEP_URL = "https://www.nationsreportcard.gov/api_documentation.aspx"

# The four NAEP series are kept separate rather than averaged into one
# "achievement" number. Averaging them would be a third weighting decision
# taken quietly, and this project's whole argument is against those.
NAEP_LABELS = {
    "mathematics_grade4": "Maths, grade 4",
    "mathematics_grade8": "Maths, grade 8",
    "reading_grade4": "Reading, grade 4",
    "reading_grade8": "Reading, grade 8",
}


def load_policy(root: Path) -> tuple[Indicator, dict]:
    """Loads state AI guidance status as a 0-100 indicator."""
    path = root / "data" / "processed" / "state_ai_policy.json"
    payload = json.loads(path.read_text())
    scoring = payload["scoring"]

    values = {
        state: float(scoring[status])
        for state, status in payload["states"].items()
        if status in scoring
    }

    indicator = Indicator(
        key="ai_policy",
        label="State AI guidance for schools",
        source=payload["source"],
        source_url=payload["source_url"],
        year=payload["source_last_updated"],
        values=values,
    )

    return indicator, payload


def load_naep_series(root: Path, *, use_cache: bool = True) -> dict[str, dict[str, float]]:
    """The NAEP figures, from the committed snapshot if there is one.

    A deployed server has no local cache, and booting should not depend on a
    call to a government API that is slow and not ours to rely on. The snapshot
    ships with the code; the live fetch stays as the fallback so local work
    still picks up a refresh.
    """
    snapshot = root / "data" / "processed" / "naep_2024.json"

    if snapshot.exists():
        payload = json.loads(snapshot.read_text())
        series = payload.get("series") or {}

        if series:
            return series

    return fetch_all(root=root, use_cache=use_cache)


def load_indicators(root: Path, *, use_cache: bool = True) -> tuple[list[Indicator], dict]:
    """Returns the indicators plus the raw policy payload for the sources page."""
    series = load_naep_series(root, use_cache=use_cache)

    indicators = [
        Indicator(
            key=key,
            label=NAEP_LABELS[key],
            source=NAEP_SOURCE,
            source_url=NAEP_URL,
            year=str(LATEST_YEAR),
            values=values,
        )
        for key, values in series.items()
    ]

    policy, payload = load_policy(root)
    indicators.append(policy)

    return indicators, payload


DEFAULT_WEIGHTS = {
    "mathematics_grade4": 0.15,
    "mathematics_grade8": 0.20,
    "reading_grade4": 0.15,
    "reading_grade8": 0.20,
    "ai_policy": 0.30,
}


def parse_weights(args, indicators: list[Indicator]) -> dict[str, float]:
    """Reads weights from a query string, falling back to the defaults.

    Anything unparseable or negative falls back rather than erroring: this
    arrives from sliders in a URL people share, and a malformed link should
    still show the index.
    """
    weights: dict[str, float] = {}

    for indicator in indicators:
        raw = args.get(f"w_{indicator.key}")

        try:
            value = float(raw) if raw is not None else DEFAULT_WEIGHTS.get(indicator.key, 0.0)
        except (TypeError, ValueError):
            value = DEFAULT_WEIGHTS.get(indicator.key, 0.0)

        weights[indicator.key] = max(0.0, min(1.0, value))

    # All-zero weights would score nothing at all; treat that as "show me the
    # default" rather than an empty page.
    if sum(weights.values()) == 0:
        return dict(DEFAULT_WEIGHTS)

    return weights


DISTRICT_NAMES = {code: name for code, (name, _state) in DISTRICTS.items()}
DISTRICT_STATE = {code: state for code, (_name, state) in DISTRICTS.items()}


def load_district_indicators(root: Path, *, use_cache: bool = True) -> tuple[list[Indicator], dict]:
    """The same index, for the urban districts NAEP assesses.

    One indicator changes meaning here and it has to be said out loud. AI
    guidance is published by state education departments, not by districts, so
    a district cannot have its own status in this dataset — it inherits its
    state's. That is a real fact about the district's policy environment and it
    is *not* evidence the district adopted anything.

    New York City is the exception, and it runs the other way. New York State
    is coded "partial" precisely because the guidance on the tracker is New
    York City Public Schools' own. For the state that is partial coverage; for
    this district it is the whole thing, so it is counted as issued.
    """
    snapshot = root / "data" / "processed" / "naep_2024_districts.json"

    if snapshot.exists():
        series = json.loads(snapshot.read_text()).get("series") or {}
    else:
        series = fetch_all(
            root=root, use_cache=use_cache,
            jurisdictions=list(DISTRICTS), kind="district",
        )

    indicators = [
        Indicator(
            key=key,
            label=NAEP_LABELS[key],
            source=NAEP_SOURCE + " (urban districts)",
            source_url=NAEP_URL,
            year=str(LATEST_YEAR),
            values=values,
        )
        for key, values in series.items()
    ]

    _state_policy, payload = load_policy(root)
    scoring = payload["scoring"]
    by_state = payload["states"]

    inherited = {}

    for code, (_name, state) in DISTRICTS.items():
        if code == "XN":
            inherited[code] = float(scoring["issued"])
            continue

        status = by_state.get(state) if state else None

        if status in scoring:
            inherited[code] = float(scoring[status])

    indicators.append(
        Indicator(
            key="ai_policy",
            label="AI guidance in the district's state",
            source=payload["source"] + " — inherited from the state",
            source_url=payload["source_url"],
            year=payload["source_last_updated"],
            values=inherited,
        )
    )

    return indicators, payload


__all__ = [
    "DEFAULT_WEIGHTS",
    "DISTRICT_NAMES",
    "DISTRICT_STATE",
    "load_district_indicators",
    "NAEP_LABELS",
    "STATES",
    "STATE_NAMES",
    "load_indicators",
    "load_policy",
    "parse_weights",
]