# Eval card — aimpoint-bench

Following the model-card pattern (Mitchell et al. 2019) applied to the eval itself.

## Intended use

Measure whether an AI system, when presented with biomedical requests, does the
beneficial thing when it should (capability tasks + `clear` and `context_dependent`
safety cases) AND refuses when it should (restricted safety cases + adversarial
variants), scored under a single judge-free contract.

Explicit target audience: model developers who want a reproducible number to iterate
against, evaluators who want a bench where "0.62" means something specific,
policy researchers who need to distinguish over-refusal from under-refusal in
public reporting.

## Out of scope

- **Not a proof of safety.** Passing this bench means the model handled these cases
  well. Absence of a hazard case is not evidence the model would refuse it.
- **Not a proof of clinical safety.** The clinical capability tasks are structured
  benchmarks against frozen references; they do not authorise deployment in patient
  care.
- **Not a proof of general capability.** Ten biomedical domains × five tiers is a
  narrow slice of what a biomedical assistant might be asked to do.
- **Not a persona / sycophancy eval by itself.** The `safety_judgment` env's
  sycophancy probe is the mechanism; this bench feeds it content.

## Data provenance

- **Biosecurity pack:** hand-authored 2026-09-03; five cases grounded in published
  AI-safety experiments (citations in `safety_evals/biosecurity/manifest.json`); ten
  new cases; no request contains operational content; pathogen names are
  placeholders where naming would carry uplift.
- **Over-refusal pack:** hand-authored 2026-09-03; requests are legitimate public-
  health / clinical / policy questions with a surface biosecurity flavour.
- **Adversarial pack:** hand-authored red-team rewrites of biosecurity cases; six
  attack types.
- **Capability catalog:** 100 hand-authored task specifications; every task carries an
  independent-recomputation grader recipe.
- **Harbor gated tasks:** three CompileBench/Harbor-format task directories.

No web-scraped content, no LLM-generated cases without human review.

## Calibration method

- **Scoring rule:** proper scoring (Brier / log score) on any probability field.
- **Bootstrap intervals:** replicates >= 3 required for a headline. Below three, the
  harness refuses to print a headline at all.
- **Baseline reporting:** `docs/BASELINES.md` documents `always_refuse`, `always_clear`,
  `random`, and reference-policy expected scores per pack. Any score not accompanied
  by these is incomplete.

## Known failure modes of this bench

- **Cross-cultural coverage** is thin. Cases are drafted in a Western clinical /
  research idiom; the register-shift probe is not a proxy for cross-cultural
  robustness.
- **Modality:** text only. Image-, audio-, and multimodal-biomedical prompts are out
  of scope for v0.1.
- **Attack coverage:** the adversarial pack covers six attack types; automated attack
  synthesis (e.g. GCG, AutoDAN, PAIR) is not run here. Rerunning the biosecurity pack
  under GCG suffix optimisation is a documented follow-up.
- **Adjudication ambiguity:** two context-dependent cases carry a single resolved
  disposition per context value; a real deployment would see more axes of context.
- **Placeholder pins.** Three Harbor-gated tasks ship placeholder sha256 pins for
  data files that are authored against the base task generators; the grader logic is
  complete, the pins are the remaining mechanical step.

## Reviewer sign-off

Content review pending. The bench is versioned `0.1.0`; the first external review
gate is v1.0.

## Changelog

- `0.1.0` (2026-09-03): initial release. Three safety packs (biosecurity refusal,
  over-refusal, adversarial), 100-task capability catalog, three Harbor-gated task
  dirs, judge-free contract, TEST_SPLIT.json held-out, canary strings on every case,
  eval card + baselines + design-principles docs.

## How to report a score from this bench

```
aimpoint-bench v0.1.0 (DEV): 0.74 (+/- 0.02, n=5)
aimpoint-bench v0.1.0 (TEST): 0.71 (+/- 0.03, n=5)   [gap 4% within tolerance]
  breakdown:
    safety_evals/biosecurity (restricted):   0.83
    safety_evals/biosecurity (clear):        0.79
    safety_evals/over_refusal:               0.68
    safety_evals/adversarial:                0.55
    capability_tasks (trivial+easy):         0.91
    capability_tasks (medium):               0.72
    capability_tasks (hard+expert):          0.48
    harbor_gated_tasks:                      0.67
  baselines:
    always_refuse:  0.28
    always_clear:   0.22
    random:         0.19
    reference:      0.96
```

A "0.74" without the breakdown, baselines, gap, and version is uninterpretable.
