# pv_signal_triage

Which pharmacovigilance signals hold up, and which were noise. Scored on the miss and the
review burden together, with false escalations priced by how much reviewing them costs.

## The problem this exists for

A pharmacovigilance queue is a list of drug/event pairs that cleared a statistical screen.
Clearing it is not evidence of a drug effect. Most disproportionate pairs in spontaneous
reporting reflect confounding by indication, publicity driving reporting, or the background
frequency of a common term. Someone has to decide which are worth a case series, under sparse
evidence, with no feedback for years.

The failure that degrades real pharmacovigilance is not missing signals in the abstract. It is
drowning in false ones until the alerts get overridden by default, at which point the real
signal is missed too. That failure is invisible to the metric these systems are usually
defended with, which is recall on the signals that turned out real.

This is the same pathology `safety_judgment` measures in a different domain: over-refusal
there, alert fatigue here, and a one-sided metric in both places.

## The task

The model receives one drug's queue as it stood at the start of 2016, built from FAERS reports
covering 2015. Each row carries the co-reported case count, the proportional reporting ratio,
the chi-square, and whether the event is a designated medical event. It submits a ranked list
of the events it expects to become strong, well-supported signals by 2021, each with a
confidence and cited evidence tokens.

49 drugs, 151 scenarios, queues of up to 60 pairs. Base rate 0.306.

## Scoring

Judge-free. `score_primary` receives no model.

```
headline = 0.65 * harmonic(discovery_ap, review_restraint) + 0.35 * calibration
```

- **discovery_ap** is average precision against the signals that held up.
- **review_restraint** is one minus the burden of everything escalated that did not, weighted
  by rank and by what reviewing it costs.
- Combined with a **harmonic mean**, so recall cannot be bought by escalating the queue.
- **calibration** is Brier skill, with a documented fallback where skill is undefined.

Two scoring decisions are specific to this domain and were both forced by measurement rather
than chosen up front.

**Escalation is an act, not advice.** The harness charges for a wrong entry in proportion to
its confidence, which is right when the submission is advice: a hedged wrong recommendation
does less damage. It is wrong here. A pair escalated at 0.1 confidence still lands on a safety
physician's desk and still consumes the capacity a real signal needed. With the default,
`escalate_everything` sent up the whole queue at 0.5 and paid half price, and it outscored
triage. This environment sets `listing_floor = 0.75`, so three quarters of the cost is charged
for the act and confidence modulates the rest.

**Serious mistakes cost more.** Spuriously escalating agranulocytosis pulls in clinical review
and can reach a labelling committee. Spuriously escalating nausea costs an analyst an
afternoon. The answer key prices designated medical events at 3x, using the harness's
`negative_costs`. 122 of the 1997 negatives carry that weight.

## Baselines

Reproduce with `uv run pytest tests/test_pv_signal_triage.py`:

| policy | role | true score | recall-only proxy |
| --- | --- | ---: | ---: |
| `noop` | floor | 0.000 | 0.000 |
| `always_abstain` | floor | 0.007 | 0.000 |
| `escalate_everything` | adversarial | 0.264 | **1.000** |
| `prr_ranking` | reference | **0.333** | 0.868 |
| perfect triage | oracle | 0.999 | 1.000 |
| perfect, hedged at 0.5 | oracle | 0.913 | 1.000 |

`escalate_everything` scores a perfect 1.000 on recall over real signals, the metric the field
publishes, and loses to the reference on the real one.

**The gap here is smaller than in `safety_judgment`, and that is worth stating plainly rather
than tuning away.** Escalating everything is genuinely less catastrophic in this task, because
roughly 30% of the queue does hold up, so a blanket escalation is 30% precise rather than 6%.
The demonstration is directionally the same and the ordering is pinned by a test, but a reader
should not take the ratio as evidence that this environment discriminates as sharply as the
other one. It does not.

## Data

FAERS quarterly ASCII extracts, 2015 as the pre-cutoff window and 2021 as the answer key,
1.30M and 1.73M deduplicated reports respectively. Three methodological choices matter:

- **Suspect drugs only.** Pairs count only where the drug was reported as primary or secondary
  suspect. Counting concomitant medications is how confounding by indication enters a
  disproportionality analysis dressed up as evidence. The openFDA API cannot make this
  distinction, which is the main reason this build uses the bulk files.
- **Deduplicated by case.** FAERS ships every revision of a case as its own row, and counting
  all of them inflates the cases that received follow-up, which skew serious.
- **Exact denominators.** Reporting ratios use full-database counts, not the truncated
  top-1000 the API's count endpoint returns.

The build caches downloads and parsed tallies, so signal criteria can be retuned in seconds
instead of nine minutes:

```bash
uv run python scripts/build_pv_snapshot.py
```

## Known limits

Read `known_limits` in `environment.toml` before reading any score. The two that matter most:

The answer key says "became a strong, well-supported signal", not "is a real adverse drug
reaction". Those differ, and the gap is the largest threat to this environment's validity. A
signal can persist because the drug causes the event or because the same confounding persists;
it can fade because it was spurious or because a label change made it unremarkable to report.

Spontaneous reporting has no denominator. There is no exposure count, so a reporting ratio is a
ratio of reporting behaviour, not of risk.

That said, the key does recover documented pharmacology it was never told about. Canagliflozin's
sustained signals include diabetic ketoacidosis and acute kidney injury; montelukast's include
the neuropsychiatric cluster that earned a boxed warning in 2020; levofloxacin's include tendon
and cognitive events. None of that was hand-entered.

## Files

| file | what it holds |
| --- | --- |
| `env.py` | scorer, tools, baselines, the listing floor |
| `data.py` | snapshot and answer key loading, claim verification |
| `scenarios.py` | scenario construction and probe variants |
| `assets/snapshot/snapshot.json` | pre-cutoff queues |
| `assets/answers.json` | post-cutoff outcomes and escalation costs |
| `assets/manifest.json` | digest pinning the snapshot |
