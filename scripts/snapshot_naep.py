"""Freezes the NAEP figures into a committed file.

The app fetches NAEP on startup and caches to data/raw/, which is gitignored.
That is right for local work and wrong for a deployment: a fresh server has no
cache, so booting would depend on four calls to a government API that is slow,
occasionally times out, and is not ours to rely on during a demo.

This writes the same numbers to data/processed/, which ships with the code, so
a deployed instance starts from a file and never touches the network.

    python scripts/snapshot_naep.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data.naep import DISTRICTS, LATEST_YEAR, fetch_all  # noqa: E402

STATE_OUT = ROOT / "data" / "processed" / "naep_2024.json"
DISTRICT_OUT = ROOT / "data" / "processed" / "naep_2024_districts.json"


def write(path, series, *, minimum, label) -> bool:
    if not series or any(len(values) < minimum for values in series.values()):
        counts = {key: len(values) for key, values in series.items()}
        print(f"Refusing to write a partial {label} snapshot: {counts}", file=sys.stderr)
        return False

    path.write_text(
        json.dumps(
            {
                "source": "NAEP, National Center for Education Statistics",
                "source_url": "https://www.nationsreportcard.gov/api_documentation.aspx",
                "year": LATEST_YEAR,
                "captured": date.today().isoformat(),
                "series": series,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(f"Wrote {path.relative_to(ROOT)}")
    for key, values in series.items():
        print(f"  {key:24} {len(values)} {label}")

    return True


def main() -> int:
    states = fetch_all(root=ROOT)

    # Three of the 28 urban districts report no usable 2024 figures, so the
    # floor is 20 rather than the full list — refusing below that still catches
    # a genuinely broken fetch.
    districts = fetch_all(
        root=ROOT, jurisdictions=list(DISTRICTS), kind="district", pause=0.5
    )

    ok = write(STATE_OUT, states, minimum=50, label="states")
    ok = write(DISTRICT_OUT, districts, minimum=20, label="districts") and ok

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
