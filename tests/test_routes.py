"""Tests that every page actually renders.

The index maths was covered from the start; the pages were not. A typo in a
Jinja template raises at render time, not at import, so the whole site could
have gone down without a single test failing — which is a bad way to find out
during a demo.

These run offline: NAEP responses are cached under data/raw/, so nothing here
touches the network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.server import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    app = create_app(ROOT)
    app.config.update(TESTING=True)

    with app.test_client() as test_client:
        yield test_client


PAGES = ["/", "/explore", "/compare", "/methodology", "/sources", "/state/MA"]


class TestPagesRender:
    @pytest.mark.parametrize("path", PAGES)
    def test_page_returns_html(self, path, client):
        response = client.get(path)

        assert response.status_code == 200
        assert b"<html" in response.data

    def test_the_causation_disclaimer_still_exists_somewhere(self, client):
        """It used to sit in the footer of every page and now lives on Method.

        The footer version was removed deliberately — it repeated on every
        screen and, once spending was added and the correlation measured, it
        was overstating the case. But the claim it guarded still matters, so
        this pins it to the page that now carries it. If that page ever loses
        it, the site is asserting a ranking with nothing qualifying it.
        """
        page = client.get("/methodology").data

        assert b"does not show that technology" in page
        assert b"correlate at" in page, "the measured correlation should be stated too"

    @pytest.mark.parametrize("path", PAGES)
    def test_page_states_its_data_vintage(self, path, client):
        assert b"NAEP 2024" in client.get(path).data


class TestWeights:
    def test_weights_in_the_url_change_the_ranking(self, client):
        default = client.get("/explore").data
        policy_only = client.get(
            "/explore?w_ai_policy=1&w_mathematics_grade4=0&w_mathematics_grade8=0"
            "&w_reading_grade4=0&w_reading_grade8=0"
        ).data

        assert default != policy_only

    def test_a_malformed_weight_falls_back_instead_of_erroring(self, client):
        # These arrive from a URL someone pasted; a bad one should still show
        # the index rather than a stack trace.
        assert client.get("/explore?w_ai_policy=banana").status_code == 200
        assert client.get("/explore?w_ai_policy=-5").status_code == 200
        assert client.get("/explore?method=nonsense").status_code == 200

    def test_all_zero_weights_still_render(self, client):
        response = client.get(
            "/explore?w_ai_policy=0&w_mathematics_grade4=0&w_mathematics_grade8=0"
            "&w_reading_grade4=0&w_reading_grade8=0"
        )

        assert response.status_code == 200


class TestStatePages:
    def test_unknown_state_is_a_404_not_a_crash(self, client):
        response = client.get("/state/ZZ")

        assert response.status_code == 404
        assert b"No state with the code" in response.data

    def test_lowercase_code_works(self, client):
        assert client.get("/state/ma").status_code == 200

    def test_profile_names_its_sources(self, client):
        assert b"nationsreportcard.gov" in client.get("/state/MA").data


class TestCompare:
    def test_same_state_twice_does_not_break(self, client):
        response = client.get("/compare?a=MA&b=MA")

        assert response.status_code == 200

    def test_unknown_state_does_not_break(self, client):
        assert client.get("/compare?a=ZZ&b=MA").status_code == 200


class TestDownloads:
    def test_csv_is_downloadable_and_carries_its_recipe(self, client):
        response = client.get("/data/index.csv")

        assert response.status_code == 200
        assert "attachment" in response.headers["Content-Disposition"]

        body = response.data.decode()

        # The weights must travel with the numbers, or a downloaded ranking
        # cannot be reproduced by whoever received it.
        assert "# weights:" in body
        assert "normalisation=" in body
        assert "Massachusetts" in body

    def test_json_carries_sources_and_the_caveat(self, client):
        payload = json.loads(client.get("/data/index.json").data)

        assert payload["rows"], "an empty export would be a silent failure"
        assert "causes educational outcomes" in payload["caveat"]
        assert all(indicator["source_url"] for indicator in payload["indicators"])

    def test_downloads_respect_the_chosen_weights(self, client):
        default = json.loads(client.get("/data/index.json").data)
        policy = json.loads(
            client.get(
                "/data/index.json?w_ai_policy=1&w_mathematics_grade4=0"
                "&w_mathematics_grade8=0&w_reading_grade4=0&w_reading_grade8=0"
            ).data
        )

        assert default["rows"][0]["state"] != policy["rows"][0]["state"]


class TestHonesty:
    """The claims the site makes about itself, checked against what it serves."""

    def test_every_state_is_ranked_exactly_once(self, client):
        payload = json.loads(client.get("/data/index.json").data)
        states = [row["state"] for row in payload["rows"]]

        assert len(states) == len(set(states)) == 50

    def test_no_score_is_invented_for_a_missing_indicator(self, client):
        payload = json.loads(client.get("/data/index.json").data)

        for row in payload["rows"]:
            # Coverage is the share of weight the state actually had data for.
            # A row claiming full coverage must have a raw value per indicator.
            if row["coverage"] == 1.0:
                assert len(row["raw"]) == len(payload["indicators"])


class TestCities:
    def test_the_page_renders(self, client):
        response = client.get("/cities")

        assert response.status_code == 200
        assert b"school districts, not cities" in response.data

    def test_weights_reorder_it_too(self, client):
        default = client.get("/cities").data
        policy_only = client.get(
            "/cities?w_ai_policy=1&w_mathematics_grade4=0&w_mathematics_grade8=0"
            "&w_reading_grade4=0&w_reading_grade8=0"
        ).data

        assert default != policy_only

    # Every district NAEP lists must appear somewhere: ranked, or named as
    # excluded. A district that quietly disappears is the failure this page's
    # coverage floor exists to prevent.
    def test_every_district_is_accounted_for(self, client):
        from app.data.loader import DISTRICT_NAMES

        page = client.get("/cities").data.decode()

        for name in DISTRICT_NAMES.values():
            assert name in page, f"{name} appears nowhere on the page"

    def test_a_district_without_test_data_is_not_ranked_first(self, client):
        page = client.get("/cities").data.decode()
        table = page.split("<tbody>")[1].split("</tbody>")[0]

        # Fresno and Shelby County report no 2024 results; scored on inherited
        # policy alone Fresno previously took first place on 30% coverage.
        assert "Fresno" not in table
        assert "Shelby County" not in table

    def test_the_excluded_are_explained(self, client):
        page = client.get("/cities").data.decode()

        assert "Not ranked" in page
        assert "no usable measures at all" in page
