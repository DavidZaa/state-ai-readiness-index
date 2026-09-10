"""Builds the index, and measures how much the index is a choice.

Two decisions turn raw indicators into a ranking, and both are arguable:

1. **Normalisation.** The inputs are not comparable. A grade-8 maths score of
   283 and a policy status of "issued" are different kinds of number on
   different scales, and putting them in the same average requires deciding
   what counts as 0 and what counts as 100. Min-max scaling makes the best
   state 100 and the worst 0, which exaggerates small real gaps; z-scores
   preserve the spread but have no natural bounds. Neither is correct.

2. **Weighting.** How much each indicator counts. Every published index picks
   weights, and the ranking follows from that pick.

Most indices report the ranking and bury both decisions. This module reports
the ranking *and* how far it moves when the decisions change, because that
movement is the honest measure of how much the ranking means.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Indicator:
    """One measured column, with enough provenance to be checked."""

    key: str
    label: str
    source: str
    source_url: str
    year: str
    # Higher is better for every indicator here. Anything where lower is
    # better would need inverting before it reached this class.
    values: dict[str, float] = field(default_factory=dict)

    def coverage(self, states: list[str]) -> float:
        present = sum(1 for s in states if s in self.values)

        return present / len(states) if states else 0.0


def min_max(values: dict[str, float]) -> dict[str, float]:
    """Scales so the best state is 100 and the worst is 0.

    Readable, and the reason most published indices use it. It also inflates
    differences: if every state sits between 78 and 82, this stretches a
    four-point spread across the full range and makes near-ties look decisive.
    """
    if not values:
        return {}

    low = min(values.values())
    high = max(values.values())

    if high == low:
        return {state: 50.0 for state in values}

    return {state: (value - low) / (high - low) * 100 for state, value in values.items()}


def z_score(values: dict[str, float]) -> dict[str, float]:
    """Scales by standard deviations from the mean, then shifts onto 0-100.

    Keeps the real shape of the distribution — a state that is genuinely
    average lands near the middle instead of being stretched to an extreme —
    at the cost of a scale with no natural end points.
    """
    if len(values) < 2:
        return {state: 50.0 for state in values}

    mean = statistics.fmean(values.values())
    deviation = statistics.pstdev(values.values())

    if deviation == 0:
        return {state: 50.0 for state in values}

    # Three standard deviations either side covers essentially the whole
    # distribution, so this rarely clips; where it does, the state was an
    # extreme outlier and the clip is recorded by the clamp.
    return {
        state: max(0.0, min(100.0, 50 + (value - mean) / deviation * (50 / 3)))
        for state, value in values.items()
    }


NORMALISERS = {"minmax": min_max, "zscore": z_score}


def score_states(
    indicators: list[Indicator],
    weights: dict[str, float],
    *,
    method: str = "minmax",
    min_coverage: float = 0.0,
) -> list[dict]:
    """Scores and ranks the states.

    A state is scored on the indicators it actually has, with its weights
    renormalised over those. Missing data is never filled in: imputing a value
    invents a measurement, and an index that quietly does that is exactly the
    thing this project is arguing against. What the reader gets instead is the
    state's coverage, so a score resting on half the evidence is visibly doing
    so.
    """
    if method not in NORMALISERS:
        raise ValueError(f"Unknown method {method!r}; expected one of {sorted(NORMALISERS)}")

    normalise = NORMALISERS[method]
    scaled = {indicator.key: normalise(indicator.values) for indicator in indicators}

    states = sorted({state for indicator in indicators for state in indicator.values})
    rows = []

    for state in states:
        total = 0.0
        used = 0.0
        present = {}

        for indicator in indicators:
            weight = weights.get(indicator.key, 0.0)
            value = scaled[indicator.key].get(state)

            if value is None or weight <= 0:
                continue

            total += value * weight
            used += weight
            present[indicator.key] = round(value, 2)

        if used == 0:
            continue

        rows.append(
            {
                "state": state,
                "score": round(total / used, 2),
                "components": present,
                "raw": {
                    indicator.key: indicator.values.get(state)
                    for indicator in indicators
                    if state in indicator.values
                },
                "coverage": round(used / sum(w for w in weights.values() if w > 0), 3)
                if any(w > 0 for w in weights.values())
                else 0.0,
            }
        )

    # Refusing to impute is not enough on its own.
    #
    # A jurisdiction scored on one weak indicator still gets a number, and that
    # number still sorts. Among the urban districts this put Fresno first on a
    # policy status inherited from its state, with no test data behind it at
    # all — a top rank resting on 30% of the evidence, which is precisely the
    # move this project exists to criticise. Below the floor a jurisdiction is
    # left out of the ranking and reported as unranked instead.
    ranked = [row for row in rows if row["coverage"] >= min_coverage]

    ranked.sort(key=lambda row: (-row["score"], row["state"]))

    for position, row in enumerate(ranked, start=1):
        row["rank"] = position

    return ranked


def below_coverage(
    indicators: list[Indicator],
    weights: dict[str, float],
    *,
    method: str = "minmax",
    min_coverage: float = 0.0,
) -> list[dict]:
    """The jurisdictions left out of the ranking, so they can be shown."""
    everything = {row["state"]: row for row in score_states(indicators, weights, method=method)}
    kept = {
        row["state"]
        for row in score_states(indicators, weights, method=method, min_coverage=min_coverage)
    }

    return sorted(
        (row for state, row in everything.items() if state not in kept),
        key=lambda row: row["state"],
    )


def rank_map(rows: list[dict]) -> dict[str, int]:
    return {row["state"]: row["rank"] for row in rows}


def rank_instability(
    indicators: list[Indicator],
    weights: dict[str, float],
    *,
    method: str = "minmax",
    trials: int | None = None,
) -> dict[str, dict]:
    """How far each state moves under defensible alternative choices.

    This is the actual contribution. A ranking that holds still across
    reasonable alternatives is telling you something about the states; one that
    reshuffles is telling you about the analyst. Reporting only the first
    ranking hides which of the two you are looking at.

    The alternatives are not random noise. Each one is a defensible index
    somebody could publish: every indicator taken alone, all of them weighted
    equally, and the whole thing under the other normalisation.
    """
    baseline = rank_map(score_states(indicators, weights, method=method))
    keys = [indicator.key for indicator in indicators]

    alternatives: list[dict[str, float]] = [dict.fromkeys(keys, 1.0)]
    alternatives.extend({key: (1.0 if key == single else 0.0) for key in keys} for single in keys)

    if trials:
        alternatives = alternatives[:trials]

    observed: dict[str, list[int]] = {state: [rank] for state, rank in baseline.items()}

    for alternative in alternatives:
        for scheme in NORMALISERS:
            for state, rank in rank_map(
                score_states(indicators, alternative, method=scheme)
            ).items():
                observed.setdefault(state, []).append(rank)

    return {
        state: {
            "baseline": baseline.get(state),
            "best": min(ranks),
            "worst": max(ranks),
            "swing": max(ranks) - min(ranks),
        }
        for state, ranks in observed.items()
    }


def random_weightings(keys: list[str], trials: int, seed: int = 0) -> list[dict[str, float]]:
    """Draws weightings uniformly from the simplex.

    Dirichlet(1) over the indicators, which is the uniform distribution over
    every weighting that sums to one. Deliberately not a spread of "reasonable"
    weightings — choosing which weightings count as reasonable is the same
    judgement the project is questioning, so the sample refuses to make it.

    Seeded, because a reader who reruns the analysis should get the same
    distribution and a screenshot should be reproducible.
    """
    generator = random.Random(seed)
    draws = []

    for _ in range(trials):
        # Exponential samples normalised to sum 1 is Dirichlet(1, ..., 1).
        raw = [generator.expovariate(1.0) for _ in keys]
        total = sum(raw) or 1.0
        draws.append({key: value / total for key, value in zip(keys, raw)})

    return draws


def rank_distribution(
    indicators: list[Indicator],
    state: str,
    *,
    trials: int = 400,
    seed: int = 0,
    progress=None,
) -> dict:
    """Where one state lands across many randomly weighted indexes.

    This is the honest version of the instability claim. Hand-picked
    alternatives can be accused of being chosen to make the point; a uniform
    sample over all possible weightings cannot, because it makes no choice at
    all.

    `progress` is called with (done, total) so the interface can report real
    work rather than animate a fake delay.
    """
    keys = [indicator.key for indicator in indicators]
    positions: list[int] = []

    for index, weights in enumerate(random_weightings(keys, trials, seed), start=1):
        for method in NORMALISERS:
            ranks = rank_map(score_states(indicators, weights, method=method))

            if state in ranks:
                positions.append(ranks[state])

        if progress and index % 20 == 0:
            progress(index, trials)

    if progress:
        progress(trials, trials)

    return _summarise_positions(state, positions)


def rank_distribution_stream(
    indicators: list[Indicator],
    state: str,
    *,
    trials: int = 2000,
    seed: int = 0,
    every: int = 50,
):
    """`rank_distribution` as a generator, so progress can be streamed.

    Yields ("progress", done, total) as it works and finally ("result", data).
    Written as a generator rather than taking a callback because the caller is
    an SSE response: it has to hand each update to the client at the moment it
    happens, not collect them and flush at the end.
    """
    keys = [indicator.key for indicator in indicators]
    positions: list[int] = []

    for index, weights in enumerate(random_weightings(keys, trials, seed), start=1):
        for method in NORMALISERS:
            ranks = rank_map(score_states(indicators, weights, method=method))

            if state in ranks:
                positions.append(ranks[state])

        if index % every == 0 or index == trials:
            yield ("progress", index, trials)

    yield ("result", _summarise_positions(state, positions), trials)


def _summarise_positions(state: str, positions: list[int]) -> dict:
    if not positions:
        return {"state": state, "trials": 0, "positions": []}

    ordered = sorted(positions)
    counts: dict[int, int] = {}

    for position in positions:
        counts[position] = counts.get(position, 0) + 1

    def percentile(fraction: float) -> int:
        return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]

    return {
        "state": state,
        "trials": len(positions),
        "best": ordered[0],
        "worst": ordered[-1],
        "median": ordered[len(ordered) // 2],
        "p10": percentile(0.10),
        "p90": percentile(0.90),
        "counts": counts,
        "mean": round(sum(ordered) / len(ordered), 1),
    }


def all_distributions(indicators: list[Indicator], *, trials: int = 500, seed: int = 0) -> dict:
    """Every state's rank distribution, from one shared set of weightings.

    Running the sample per state would repeat identical work fifty times: each
    ranking already places all fifty states, so one pass yields every
    distribution. This is what makes an honest site-wide instability figure
    cheap enough to compute at startup.
    """
    keys = [indicator.key for indicator in indicators]
    positions: dict[str, list[int]] = {}

    for weights in random_weightings(keys, trials, seed):
        for method in NORMALISERS:
            for state, rank in rank_map(score_states(indicators, weights, method=method)).items():
                positions.setdefault(state, []).append(rank)

    return {state: _summarise_positions(state, ranks) for state, ranks in positions.items()}
