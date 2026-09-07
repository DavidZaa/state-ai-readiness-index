"""Flask app for the State AI Readiness Index.

Server-rendered, because the point of the site is the argument and the
evidence, and both should be in the HTML a reader receives rather than
assembled afterwards by script.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
from datetime import date
from pathlib import Path

from flask import Flask, Response, render_template, request

from app.data.loader import (
    DEFAULT_WEIGHTS,
    STATE_NAMES,
    load_indicators,
    parse_weights,
)
from app.charts import SERIES_A, SERIES_B, comparison_series, policy_strips
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
        # The range chart shows the widest travellers first, because the
        # argument is about how far a position can move.
        spread = sorted(swings.items(), key=lambda kv: -kv[1]["swing"])[:12]

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
            spread=spread,
            swings=swings,
            strips=policy_strips(indicators, STATE_NAMES),
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
            series=comparison_series(indicators, lookup.get(a), lookup.get(b)),
        )

    # A state's own page. BrainBow let you look up one country rather than
    # read the whole table, and the same is true here: most people arrive
    # wanting one state, not fifty.
    @app.route("/state/<code>")
    def state_profile(code):
        code = code.upper()
        weights, method, rows = context(request.args)
        lookup = {row["state"]: row for row in rows}
        row = lookup.get(code)
        swings = rank_instability(indicators, weights, method=method) if row else {}

        return render_template(
            "state.html",
            row=row,
            code=code,
            names=STATE_NAMES,
            states=sorted(lookup),
            indicators=indicators,
            weights=weights,
            swing=swings.get(code),
            total=len(rows),
        ), (200 if row else 404)

    # Every serious data tool lets you take the data away and check it. These
    # export exactly what the reader is looking at — the weights and the
    # normalisation travel in the payload, so a downloaded ranking can be
    # reproduced rather than merely quoted.
    def _export(args):
        weights, method, rows = context(args)

        return weights, method, rows, rank_instability(indicators, weights, method=method)

    @app.route("/data/index.csv")
    def download_csv():
        weights, method, rows, swings = _export(request.args)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        keys = [indicator.key for indicator in indicators]

        writer.writerow(["# State AI Readiness Index"])
        writer.writerow([f"# generated {date.today().isoformat()}  normalisation={method}"])
        writer.writerow(["# weights: " + ", ".join(f"{k}={weights[k]}" for k in keys)])
        writer.writerow(["# scores are computed, not measured — see /methodology"])
        writer.writerow(
            ["rank", "state_code", "state", "score", "rank_best", "rank_worst", "swing", "coverage"]
            + [f"raw_{key}" for key in keys]
        )

        for row in rows:
            swing = swings.get(row["state"], {})
            writer.writerow(
                [
                    row["rank"], row["state"], STATE_NAMES.get(row["state"], row["state"]),
                    row["score"], swing.get("best", ""), swing.get("worst", ""),
                    swing.get("swing", ""), row["coverage"],
                ]
                + [row["raw"].get(key, "") for key in keys]
            )

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=state-ai-readiness-index.csv"},
        )

    @app.route("/data/index.json")
    def download_json():
        weights, method, rows, swings = _export(request.args)

        payload = {
            "name": "State AI Readiness Index",
            "generated": date.today().isoformat(),
            "normalisation": method,
            "weights": weights,
            "caveat": (
                "Scores are computed from confounded proxy indicators and do not show "
                "that technology causes educational outcomes."
            ),
            "indicators": [
                {
                    "key": i.key, "label": i.label, "source": i.source,
                    "source_url": i.source_url, "year": i.year,
                    "states_covered": len(i.values),
                }
                for i in indicators
            ],
            "rows": [
                {**row, "name": STATE_NAMES.get(row["state"]),
                 "instability": swings.get(row["state"])}
                for row in rows
            ],
        }

        return Response(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=state-ai-readiness-index.json"},
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
    app.jinja_env.globals["series_a"] = SERIES_A
    app.jinja_env.globals["series_b"] = SERIES_B
    app.jinja_env.globals["data_vintage"] = {
        "naep": "2024",
        "policy": policy_payload.get("source_last_updated", "2026"),
        "built": date.today().isoformat(),
    }
    app.jinja_env.globals["repo_url"] = "https://github.com/DavidZaa/state-ai-readiness-index"

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
