"""Flask app for the State AI Readiness Index.

Server-rendered, because the point of the site is the argument and the
evidence, and both should be in the HTML a reader receives rather than
assembled afterwards by script.
"""

from __future__ import annotations

import statistics
from pathlib import Path

from flask import Flask, render_template, request

from app.data.loader import (
    DEFAULT_WEIGHTS,
    STATE_NAMES,
    load_indicators,
    parse_weights,
)
from app.index_model import rank_instability, score_states

ROOT = Path(__file__).resolve().parents[1]


def create_app(root: Path = ROOT) -> Flask:
    app = Flask(__name__)

    # Loaded once at startup. NAEP publishes every two years and the policy
    # file is committed, so nothing here changes between requests — refetching
    # per request would just make a public service carry our traffic.
    indicators, policy_payload = load_indicators(root)
    by_key = {indicator.key: indicator for indicator in indicators}

    def context(args):
        weights = parse_weights(args, indicators)
        method = args.get("method", "minmax")

        if method not in ("minmax", "zscore"):
            method = "minmax"

        rows = score_states(indicators, weights, method=method)

        return weights, method, rows

    @app.route("/")
    def index():
        weights, method, rows = context(request.args)
        swings = rank_instability(indicators, weights, method=method)
        median_swing = statistics.median(s["swing"] for s in swings.values()) if swings else 0
        most_unstable = sorted(swings.items(), key=lambda kv: -kv[1]["swing"])[:3]

        return render_template(
            "index.html",
            rows=rows[:10],
            total=len(rows),
            indicators=indicators,
            weights=weights,
            method=method,
            names=STATE_NAMES,
            median_swing=median_swing,
            most_unstable=most_unstable,
        )

    @app.route("/explore")
    def explore():
        weights, method, rows = context(request.args)
        swings = rank_instability(indicators, weights, method=method)

        return render_template(
            "explore.html",
            rows=rows,
            indicators=indicators,
            weights=weights,
            method=method,
            names=STATE_NAMES,
            swings=swings,
            defaults=DEFAULT_WEIGHTS,
        )

    @app.route("/compare")
    def compare():
        weights, method, rows = context(request.args)
        lookup = {row["state"]: row for row in rows}
        ordered = sorted(lookup)

        a = request.args.get("a", "MA" if "MA" in lookup else (ordered[0] if ordered else None))
        b = request.args.get("b", "TX" if "TX" in lookup else (ordered[-1] if ordered else None))
        swings = rank_instability(indicators, weights, method=method)

        return render_template(
            "compare.html",
            a=lookup.get(a),
            b=lookup.get(b),
            a_code=a,
            b_code=b,
            states=ordered,
            indicators=indicators,
            weights=weights,
            method=method,
            names=STATE_NAMES,
            swings=swings,
        )

    @app.route("/methodology")
    def methodology():
        return render_template(
            "methodology.html",
            indicators=indicators,
            defaults=DEFAULT_WEIGHTS,
            policy=policy_payload,
        )

    @app.route("/sources")
    def sources():
        coverage = {
            indicator.key: {
                "have": len(indicator.values),
                "missing": sorted(set(STATE_NAMES) - set(indicator.values)),
            }
            for indicator in indicators
        }

        return render_template(
            "sources.html",
            indicators=indicators,
            coverage=coverage,
            policy=policy_payload,
            names=STATE_NAMES,
        )

    @app.template_filter("pct")
    def _pct(value: float) -> str:
        return f"{value * 100:.0f}%"

    @app.template_filter("ordinal")
    def _ordinal(value: int) -> str:
        """1st, 2nd, 3rd, 4th — including the 11th/12th/13th exceptions."""
        number = int(value)
        suffix = "th"

        if number % 100 not in (11, 12, 13):
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

        return f"{number}{suffix}"

    app.jinja_env.globals["by_key"] = by_key

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
