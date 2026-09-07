# What this project is

## In one line

A ranking of US states on how ready they are for AI in schools — built so you can
see how much the ranking depends on choices the author made.

## The problem

Every few months someone publishes a ranking of states on AI readiness or digital
equity, and those rankings move attention and money.

Every one of them works the same way. Pick some things to measure. Decide how much
each one counts. Add them up. Publish the order.

The second step is the problem. Nobody measures how much test scores should count
against internet access — somebody picks a number. Change that number and the order
changes. Most reports bury the weights in an appendix, if they publish them at all,
and present the result as though it were discovered rather than chosen.

## What this does

It builds the same kind of ranking from public data — test scores and whether a state
has published AI guidance for schools — and then does the thing the reports don't:
it hands you the weights.

Move a slider and watch the table reorder. Then, for any state, it builds a thousand
rankings with the weights picked at random and shows you every position that state
landed on. If a state stays put, its rank means something. If it bounces from 9th to
33rd, it doesn't.

Every number links to where it came from, and where a state is missing data, the site
says so rather than guessing.

## What it refuses to claim

It does not show that technology or AI policy causes better schools. The measures are
collected separately and are tangled together — richer states tend to do better on all
of them at once. The site shows this directly: states with no AI guidance have slightly
higher test scores than states with it.

## Why it holds up as research

The contribution is not the ranking. It's the measurement of how unstable that ranking
is: the typical state moves 14 places between its better and worse outcomes, and 20
across its full range, without a single number about the states changing.

That is a real, checkable claim about how much composite rankings can be trusted, and
it is arguable — which is what makes it worth arguing about.

## Still open

- **The name.** The folder says State AI Readiness Index. The original repo was called
  EduCity, which implies cities; the unit here is states.
- **Internet and device access** belongs in the ranking and is not in it yet. The
  Census API now needs a key.
- **Nobody is credited.** Every comparable tool names its authors.
