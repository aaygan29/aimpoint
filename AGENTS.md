# Notes for coding agents working in this repo

If you are an AI agent asked to add or modify an environment here, read this first. Several
rules in this repo exist to prevent failure modes that are easy to introduce and hard to see.

## Hard rules

1. **Never put an LLM judge in a primary scorer.** `score_primary` receives no model, on
   purpose. Do not import `get_model`, do not call one through a helper, do not add a
   "just for the tricky cases" fallback. Validation traps model acquisition at runtime and
   will fail. Judged logic goes in `score_secondary`.

2. **Never parse prose to decide what a model did.** All actions arrive as validated tool
   calls. If you are writing a regex against a model completion, stop.

3. **Never call a network API at eval time.** Data comes from checksum-pinned snapshots.
   Fetching belongs in `scripts/build_snapshot.py`, which runs once. CI greps for network
   client imports under `environments/` and fails the build.

4. **Never weaken a baseline to make a score look better.** If a model does not beat the
   reference policy, report it. That is a finding, not a bug.

5. **Never populate a test split by reusing dev scenarios.** An empty held-out split is
   honest; a duplicated one is not.

## Things that look like improvements and are not

- **Normalising a penalty by submitted list length.** It lets padding dilute the penalty.
  This exact bug was in `negative_burden` and is now pinned by
  `test_padding_does_not_dilute_the_negative_penalty`.
- **Returning 0.0 from a probe that had nothing to measure.** It dilutes the average and
  makes "never tested" read as "nothing found". Return the not-applicable marker.
- **Folding `UNVERIFIABLE` into `CONTRADICTED`.** It penalises citing true things the
  snapshot does not cover, which teaches reticence rather than accuracy.
- **Reporting a capitulation rate as a sycophancy score.** Without the
  pressure-toward-correct condition, a model that never updates scores perfectly, and
  stubbornness is not integrity.
- **Letting a single-replicate run print a headline.** The refusal in `RunAggregate.headline`
  is deliberate. Do not add a bypass flag.

## Before you claim an environment works

Run all of these and report the actual output rather than that you ran them:

```bash
uv run aimpoint validate
uv run pytest
uv run ruff check .
```

Then verify the ground truth **by hand**. Sample the answer key and check whether a domain
expert would agree with it. A snapshot that builds cleanly and is subtly wrong produces
confident meaningless scores, and no automated check catches it.

Audit the split in both directions: can every correct answer be named from what the model was
shown, and does some incidental property separate the answers from the field? Both bugs
shipped in this repo's first snapshot. Copy the `audit()` pattern in
`scripts/build_snapshot.py`.

## The asymmetry gate

Before proposing an environment, write the most harmful thing a model that maxed it could do
better than before. If that sentence is easy to write, redesign rather than argue. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the worked rejection.

## Style

No em dashes. Comments explain why a non-obvious choice was made, not what the line does.
Match the surrounding density; this codebase comments the reasoning behind design decisions
and leaves mechanical code bare.
