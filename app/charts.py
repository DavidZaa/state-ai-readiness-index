"""Prepares chart-ready data.

Kept out of the templates so the geometry can be tested and so a Jinja file
never does arithmetic. Everything returns plain dicts with coordinates already
resolved to percentages, which the SVG and the CSS both consume directly.

Chart colours are not the site accent. The interface accent is a deliberately
deep, desaturated blue chosen to look like print; chart marks need more
lightness and chroma than that to stay separable, including under colour-vision
deficiency. So the two-series pair below is a chart-only palette, validated
rather than eyeballed.
"""

from __future__ import annotations

from app.index_model import Indicator, min_max

# Validated for a light surface: CVD separation ΔE 22.6 (protan), normal-vision
# ΔE 27.4, both above 3:1 contrast against paper.
SERIES_A = "#2f72b8"
SERIES_B = "#c06616"

POLICY_GROUPS = [
    ("issued", "Guidance issued", 100.0),
    ("partial", "Partial (city only)", 50.0),
    ("none", "No guidance found", 0.0),
]


def achievement_scores(indicators: list[Indicator]) -> dict[str, float]:
    """Mean of the normalised NAEP series — the results half of the index.

    Averaging the four test series is itself a weighting decision, and it is
    made here only so the policy relationship can be drawn on one axis. The
    index proper keeps them separate for exactly this reason.
    """
    naep = [i for i in indicators if i.key != "ai_policy"]

    if not naep:
        return {}

    scaled = [min_max(indicator.values) for indicator in naep]
    states = sorted({state for values in scaled for state in values})

    means = {}

    for state in states:
        present = [values[state] for values in scaled if state in values]

        if present:
            means[state] = sum(present) / len(present)

    return means


def policy_strips(indicators: list[Indicator], names: dict[str, str]) -> list[dict]:
    """Achievement laid out as one strip per policy status.

    A scatter would be the obvious reach and the wrong form: the policy
    indicator takes three values, so a scatter draws three columns of dots
    pretending to be a cloud. Separate strips say what the data actually is,
    and put the overlap between groups where it can be seen — which is the
    honest answer to whether guidance goes with better results.
    """
    policy = next((i for i in indicators if i.key == "ai_policy"), None)
    achievement = achievement_scores(indicators)

    if policy is None or not achievement:
        return []

    strips = []

    for key, label, value in POLICY_GROUPS:
        members = [
            {
                "state": state,
                "name": names.get(state, state),
                "x": round(achievement[state], 2),
            }
            for state, score in policy.values.items()
            if score == value and state in achievement
        ]

        members.sort(key=lambda member: member["x"])
        xs = [member["x"] for member in members]

        strips.append(
            {
                "key": key,
                "label": label,
                "members": members,
                "count": len(members),
                "median": round(sorted(xs)[len(xs) // 2], 1) if xs else None,
            }
        )

    return strips


def comparison_series(
    indicators: list[Indicator],
    a: dict | None,
    b: dict | None,
) -> list[dict]:
    """Two states across every indicator, normalised so one axis can hold them.

    Raw values cannot share an axis — a reading scale score near 220 and a
    policy status of 100 are different units — so the bars show the normalised
    position and the raw figure is printed beside it.
    """
    if not a or not b:
        return []

    rows = []

    for indicator in indicators:
        scaled = min_max(indicator.values)

        rows.append(
            {
                "label": indicator.label,
                "a": {
                    "scaled": round(scaled.get(a["state"], 0), 1),
                    "raw": indicator.values.get(a["state"]),
                },
                "b": {
                    "scaled": round(scaled.get(b["state"], 0), 1),
                    "raw": indicator.values.get(b["state"]),
                },
            }
        )

    return rows
