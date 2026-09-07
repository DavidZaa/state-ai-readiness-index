# State AI Readiness Index

A sourced index of how ready each U.S. state is to use AI in education — and an
argument that any such index is a choice, not a measurement.

## The point

Reports rank states on "AI readiness" every few months, and the rankings move
attention and funding. Nearly all of them combine indicators using weights
somebody picked, then present the result as though it were discovered rather
than authored.

This one hands the weights to the reader, and reports what happens when they
move. On the current data, **the median state shifts 26 places out of 50** when
the index is rebuilt with a different but equally defensible recipe. Alaska
ranks 44th by default, 1st on policy alone, and 49th on grade-8 reading alone —
same states, same data, same year.

That spread is the finding. A ranking that holds still tells you about the
states; one that reshuffles tells you about whoever built it.

## Data

| Indicator | Source | Year | Coverage |
| --- | --- | --- | --- |
| Maths, grades 4 and 8 | NAEP, via the public NCES Data Service | 2024 | 50/50 |
| Reading, grades 4 and 8 | NAEP, via the public NCES Data Service | 2024 | 50/50 |
| State AI guidance for schools | AI for Education state tracker | to Aug 2026 | 50/50 |

NAEP figures are fetched live and cached under `data/raw/`. The policy dataset
is committed at `data/processed/state_ai_policy.json`, with its coding rules
written down, so any change to it is a reviewable diff.

Broadband and device access belong in the index and are **not yet loaded** — the
Census ACS API now requires a key. The site lists that gap rather than dropping
it from the description.

## What it does not claim

It does not show that technology or AI policy causes educational outcomes. The
indicators are separately measured and heavily confounded: wealthier states tend
to do better on all of them at once, and nothing here separates that out.

## Running it

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
PYTHONPATH=. ./.venv/bin/python -m flask --app app.server run --port 8000
```

Then open http://localhost:8000. The first start fetches NAEP and caches it;
later starts read the cache.

```bash
./.venv/bin/python -m pytest tests/ -q      # index maths
```

## Layout

```text
app/
  server.py            Flask routes
  index_model.py       normalisation, weighting, rank instability
  data/
    naep.py            NAEP Data Service client, cached to disk
    loader.py          assembles indicators with their provenance
  templates/           Jinja pages
  static/              styles, Vanta background, slider script
data/
  raw/                 cached API responses (gitignored)
  processed/           committed datasets the published index rests on
tests/                 index maths
docs/statement.md      what this project is for
```
