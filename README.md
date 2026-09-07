# State AI Readiness Index

A ranking of US states on how ready they are for AI in schools, built so you can
see how much the ranking depends on choices someone made.

## The point

Every few months someone publishes a ranking like this, and those rankings move
attention and money. They all work the same way: pick some things to measure,
decide how much each one counts, add them up, publish the order.

The second step is the problem. Nobody measures how much test scores should
count against internet access — somebody picks a number, and changing it changes
the order. Most reports bury that choice in an appendix.

This one hands you the weights instead, then measures how much they matter. Rank
all 50 states a thousand times with the weights drawn at random and **the typical
state moves 14 places** between its better and worse outcomes, and 20 across its
full range — without a single number about the states changing.

That instability is the finding, and it is the point of the site.

## Data

| Indicator | Source | Year | Coverage |
| --- | --- | --- | --- |
| Maths, grades 4 and 8 | NAEP, via the public NCES Data Service | 2024 | 50/50 |
| Reading, grades 4 and 8 | NAEP, via the public NCES Data Service | 2024 | 50/50 |
| State AI guidance for schools | AI for Education state tracker | to Aug 2026 | 50/50 |

Instability is measured by sampling: a thousand weightings drawn uniformly at
random, rather than a handful of hand-picked alternatives. Hand-picked ones
turned out to overstate the movement badly — including "one indicator alone" as
an alternative made Alaska look like it could reach 1st, when no random weighting
ever puts it above 31st.

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

## Putting it online

The app reads its data from committed files, so a deployed server never calls the
NAEP API at startup. Refresh the data with `python scripts/snapshot_naep.py` and
commit the result.

```bash
gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app.server:app
```

`Procfile` and `render.yaml` are set up for Render; the same start command works
on Railway, Fly and Heroku. Set `SARI_AUTHOR`, `SARI_AUTHOR_URL` and
`SARI_REPO_URL` so the footer credits someone and links to real code.

Note that Render's free plan sleeps after 15 minutes idle and takes about a
minute to wake — fine for a link you send occasionally, poor for a judge
clicking through. PythonAnywhere's free tier stays awake and suits Flask well.

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
