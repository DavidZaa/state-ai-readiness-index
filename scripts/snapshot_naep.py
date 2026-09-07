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

from app.data.naep import LATEST_YEAR, fetch_all  # noqa: E402

OUTPUT = ROOT / "data" / "processed" / "naep_2024.json"


def main() -> int:
    series = fetch_all(root=ROOT)

    if not series or any(len(values) < 50 for values in series.values()):
        counts = {key: len(values) for key, values in series.items()}
        print(f"Refusing to write a partial snapshot: {counts}", file=sys.stderr)
        return 1

    payload = {
        "source": "NAEP, National Center for Education Statistics",
        "source_url": "https://www.nationsreportcard.gov/api_documentation.aspx",
        "year": LATEST_YEAR,
        "captured": date.today().isoformat(),
        "series": series,
    }

    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    for key, values in series.items():
        print(f"  {key:24} {len(values)} states")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
