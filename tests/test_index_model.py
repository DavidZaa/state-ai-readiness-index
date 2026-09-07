"""Tests for the index maths.

This is the part that has to be right. Everything else on the site presents
what these functions decide, so a quiet error here would be published as a
finding about real states.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.index_model import (  # noqa: E402
    Indicator,
    min_max,
    rank_instability,
    rank_map,
    score_states,
    z_score,
)


def indicator(key: str, values: dict[str, float]) -> Indicator:
    return Indicator(key=key, label=key, source="test", source_url="", year="2024", values=values)


class TestMinMax:
    def test_puts_the_best_at_100_and_the_worst_at_0(self):
        scaled = min_max({"A": 10, "B": 20, "C": 30})

        assert scaled["A"] == 0
        assert scaled["C"] == 100
        assert scaled["B"] == 50

    def test_gives_everyone_the_midpoint_when_nothing_separates_them(self):
        assert min_max({"A": 5, "B": 5}) == {"A": 50.0, "B": 50.0}

    def test_handles_no_data(self):
        assert min_max({}) == {}

    def test_stretches_a_narrow_real_spread_across_the_whole_scale(self):
        # The documented weakness, pinned so it stays a known property rather
        # than becoming a surprise: four real points become the full range.
        scaled = min_max({"A": 78, "B": 80, "C": 82})

        assert scaled["A"] == 0
        assert scaled["C"] == 100


class TestZScore:
    def test_puts_the_mean_at_the_midpoint(self):
        scaled = z_score({"A": 10, "B": 20, "C": 30})

        assert scaled["B"] == 50

    def test_keeps_a_narrow_spread_narrow(self):
        # The same input min-max stretched to 0-100 stays clustered here, which
        # is the whole reason both methods are offered.
        scaled = z_score({"A": 78, "B": 80, "C": 82})

        assert 25 < scaled["A"] < 50
        assert 50 < scaled["C"] < 75

    def test_stays_inside_the_scale(self):
        scaled = z_score({"A": 1, "B": 2, "C": 3, "D": 400})

        assert all(0 <= value <= 100 for value in scaled.values())

    def test_handles_degenerate_input(self):
        assert z_score({"A": 5}) == {"A": 50.0}
        assert z_score({"A": 5, "B": 5}) == {"A": 50.0, "B": 50.0}


class TestScoreStates:
    def test_ranks_by_weighted_score(self):
        rows = score_states(
            [indicator("a", {"CA": 10, "TX": 20, "NY": 30})],
            {"a": 1.0},
        )

        assert [row["state"] for row in rows] == ["NY", "TX", "CA"]
        assert [row["rank"] for row in rows] == [1, 2, 3]

    def test_weights_actually_change_the_order(self):
        indicators = [
            indicator("maths", {"CA": 100, "TX": 0}),
            indicator("policy", {"CA": 0, "TX": 100}),
        ]

        maths_first = score_states(indicators, {"maths": 1.0, "policy": 0.0})
        policy_first = score_states(indicators, {"maths": 0.0, "policy": 1.0})

        assert maths_first[0]["state"] == "CA"
        assert policy_first[0]["state"] == "TX"

    # Imputing a missing value invents a measurement. A state is scored on what
    # it has, and the reader is told how much that was.
    def test_scores_a_state_on_the_indicators_it_has(self):
        indicators = [
            indicator("a", {"CA": 100, "TX": 50, "NY": 0}),
            indicator("b", {"CA": 0}),
        ]

        rows = {row["state"]: row for row in score_states(indicators, {"a": 0.5, "b": 0.5})}

        # Texas sits midway on indicator a and has nothing on b, so its score
        # is indicator a alone rather than being dragged toward an invented
        # middle — and its coverage says the score rests on half the evidence.
        assert rows["TX"]["score"] == 50
        assert rows["TX"]["coverage"] == 0.5
        assert rows["CA"]["coverage"] == 1.0

    def test_never_invents_a_value_for_a_missing_state(self):
        rows = score_states([indicator("a", {"CA": 100, "TX": 50})], {"a": 1.0})

        assert {row["state"] for row in rows} == {"CA", "TX"}
        assert all("b" not in row["components"] for row in rows)

    def test_drops_a_state_with_nothing_weighted(self):
        indicators = [indicator("a", {"CA": 100}), indicator("b", {"TX": 100})]
        rows = score_states(indicators, {"a": 1.0, "b": 0.0})

        assert [row["state"] for row in rows] == ["CA"]

    def test_breaks_ties_predictably(self):
        rows = score_states([indicator("a", {"TX": 50, "CA": 50})], {"a": 1.0})

        assert [row["state"] for row in rows] == ["CA", "TX"]

    def test_rejects_an_unknown_method(self):
        try:
            score_states([indicator("a", {"CA": 1})], {"a": 1.0}, method="nonsense")
        except ValueError as error:
            assert "nonsense" in str(error)
        else:
            raise AssertionError("an unknown normaliser must not silently pass")


class TestRankInstability:
    def test_reports_no_swing_when_a_state_leads_on_everything(self):
        indicators = [
            indicator("a", {"CA": 100, "TX": 50, "NY": 0}),
            indicator("b", {"CA": 100, "TX": 50, "NY": 0}),
        ]

        swings = rank_instability(indicators, {"a": 0.5, "b": 0.5})

        assert swings["CA"]["swing"] == 0
        assert swings["CA"]["best"] == 1

    # The finding the project exists to show: a state can top one defensible
    # index and sit bottom of another, from the same data.
    def test_reports_a_full_swing_when_the_indicators_disagree(self):
        indicators = [
            indicator("a", {"CA": 100, "TX": 0}),
            indicator("b", {"CA": 0, "TX": 100}),
        ]

        swings = rank_instability(indicators, {"a": 0.5, "b": 0.5})

        assert swings["CA"]["best"] == 1
        assert swings["CA"]["worst"] == 2
        assert swings["CA"]["swing"] == 1

    def test_includes_the_baseline_rank(self):
        indicators = [indicator("a", {"CA": 100, "TX": 0})]
        swings = rank_instability(indicators, {"a": 1.0})

        assert swings["CA"]["baseline"] == 1
        assert swings["TX"]["baseline"] == 2


class TestRankMap:
    def test_maps_states_to_positions(self):
        rows = score_states([indicator("a", {"CA": 10, "TX": 20})], {"a": 1.0})

        assert rank_map(rows) == {"TX": 1, "CA": 2}
