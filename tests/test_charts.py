"""Tests for the chart data.

The strip plot is the chart that makes the project's central caveat visible,
so its grouping has to be right — a state filed under the wrong policy status
would misstate the relationship the reader is being asked to judge.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.charts import achievement_scores, comparison_series, policy_strips  # noqa: E402
from app.index_model import Indicator  # noqa: E402


def indicator(key, values):
    return Indicator(key=key, label=key, source="t", source_url="", year="2024", values=values)


NAMES = {"CA": "California", "TX": "Texas", "NY": "New York"}


def sample():
    return [
        indicator("mathematics_grade8", {"CA": 10, "TX": 20, "NY": 30}),
        indicator("reading_grade8", {"CA": 10, "TX": 20, "NY": 30}),
        indicator("ai_policy", {"CA": 100.0, "TX": 0.0, "NY": 50.0}),
    ]


class TestAchievement:
    def test_averages_the_test_series_only(self):
        scores = achievement_scores(sample())

        # Policy is excluded, so the two identical NAEP series average to
        # themselves: bottom 0, top 100.
        assert scores["CA"] == 0
        assert scores["NY"] == 100

    def test_survives_having_no_test_series(self):
        assert achievement_scores([indicator("ai_policy", {"CA": 100.0})]) == {}


class TestPolicyStrips:
    def test_files_each_state_under_its_status(self):
        strips = {strip["key"]: strip for strip in policy_strips(sample(), NAMES)}

        assert [m["state"] for m in strips["issued"]["members"]] == ["CA"]
        assert [m["state"] for m in strips["partial"]["members"]] == ["NY"]
        assert [m["state"] for m in strips["none"]["members"]] == ["TX"]

    def test_always_returns_all_three_rows(self):
        # An empty row is information — it says no state is in that group —
        # so the row must not be dropped just because it is empty.
        strips = policy_strips(
            [
                indicator("mathematics_grade8", {"CA": 10, "TX": 20}),
                indicator("ai_policy", {"CA": 100.0, "TX": 100.0}),
            ],
            NAMES,
        )

        assert [strip["key"] for strip in strips] == ["issued", "partial", "none"]

        empty = {strip["key"]: strip for strip in strips}

        assert empty["partial"]["count"] == 0
        assert empty["none"]["count"] == 0

    def test_orders_members_left_to_right(self):
        members = policy_strips(
            [
                indicator("mathematics_grade8", {"CA": 30, "TX": 10, "NY": 20}),
                indicator("ai_policy", {"CA": 100.0, "TX": 100.0, "NY": 100.0}),
            ],
            NAMES,
        )[0]["members"]

        assert [m["x"] for m in members] == sorted(m["x"] for m in members)

    def test_returns_nothing_without_a_policy_indicator(self):
        assert policy_strips([indicator("mathematics_grade8", {"CA": 10})], NAMES) == []


class TestComparisonSeries:
    def test_pairs_every_indicator(self):
        rows = comparison_series(sample(), {"state": "CA"}, {"state": "NY"})

        assert len(rows) == 3
        assert rows[0]["a"]["raw"] == 10
        assert rows[0]["b"]["raw"] == 30

    def test_returns_nothing_without_both_states(self):
        assert comparison_series(sample(), None, {"state": "NY"}) == []
        assert comparison_series(sample(), {"state": "CA"}, None) == []
