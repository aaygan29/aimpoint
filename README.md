# Aimpoint

**Open-source environments for the capabilities we want AI to have.**

[![License](https://img.shields.io/badge/license-Apache%202.0-black.svg)](LICENSE)
[![Environments](https://img.shields.io/badge/environments-1-white.svg)](environments/)
[![Built on Inspect](https://img.shields.io/badge/built%20on-Inspect-105864.svg)](https://inspect.aisi.org.uk/)

Model evaluation is lopsided. We have well-developed evals for dangerous capabilities,
bioweapons uplift, cyber offense, and almost nothing measuring the capabilities we actively
*want* a frontier model to have. Labs optimize for what benchmarks measure, so this is a
gap with consequences: nobody is aiming at the good outcomes because nobody built the
target.

This repo builds those targets. It follows the framing in BlueDot Impact's
[Give AI companies something to aim at](https://blog.bluedot.org/p/give-ai-companies-something-to-aim),
including the mechanical point that an eval and an RL environment are the same object seen
twice: **the eval's scoring rubric becomes the environment's reward function.** Everything
here is built to survive that, because a rubric that is merely descriptive becomes a
specification the moment someone trains on it.

---

## The three rules

Most eval repos treat these as good practice. Here they are enforced by the harness, and
`aimpoint validate` fails your pull request if you break them.

**1. Headline scores are judge-free.** A primary scorer receives a scenario, a typed
submission, and frozen data. It is handed no model, so it cannot become an LLM judge by
accident, and validation additionally traps model acquisition at runtime to catch a scorer
reaching for one through a global. LLM judges are allowed only as clearly-labeled secondary
metrics that can never enter the headline. This is what makes a number reproducible across
runs and comparable across providers.

**2. Baselines are mandatory.** Every environment ships a no-op floor and a non-trivial
reference policy. A bare 0.62 is not a result: it could be excellent, or worse than doing
nothing, and the reader has no way to tell. Scores are reported normalized so that 0.0
means "matched doing nothing" and 1.0 means "matched the obvious approach".

**3. Every environment must argue that it is beneficial.** Not assume it. Each one declares
a `capability_claim`, a `bottleneck_claim`, and an `asymmetry_claim` naming the closest
offensive analogue of its capability and explaining why competence does not transfer. The
article's own test is the bar: "better at Python" is a general capability wearing safety
language; "better at TransformerLens" unblocks a specific safety bottleneck.

## What the harness gives you for free

Contributing an environment should mean writing domain logic, not re-deriving how to
measure sycophancy. Four probes are cross-cutting, so every environment inherits them:

| Probe | Question | Why it is not the obvious metric |
| --- | --- | --- |
| **Sycophancy** | Does it change its answer because it was pushed, or because it was shown a reason? | Capitulation rate alone rewards stubbornness. Scenarios push toward wrong *and* right answers with an identical message template, and the reported `sycophancy_index` is the difference. |
| **Abstention** | Did it find out what it needed before committing, and decline when it should have? | Both failure modes are scored separately. A metric that only punishes answering-past-a-hole rewards reflexive hedging, so an `always_abstain` baseline is shipped to keep it honest. |
| **Fabrication** | Are the claims justifying the answer actually true? | Claims are cited as structured tokens checked against frozen data. `UNVERIFIABLE` is kept distinct from `CONTRADICTED`, because penalizing the former teaches reticence rather than accuracy. |
| **Shift** | Does it know when it has left the ground it handles well? | Degradation alone is weak. The headline is `overconfidence_under_shift`: how much worse it got, minus how much less confident it became. |

Plus: calibration scored under a proper scoring rule with the Murphy decomposition,
bootstrap intervals over replicates, checksum-pinned data snapshots, and a **proxy gap**
that measures specification gaming directly, by having each environment write down the
flawed metric a hurried designer would have shipped and reporting the difference.

## Environments

| Area | Environment | Status | Scenarios | Judge-free |
| --- | --- | --- | --- | --- |
| biomedical-rd | [`target_triage`](environments/biomedical_rd/target_triage/) | reference | 21 | yes |

Areas follow the article's list, extended where a contribution needed a home:
`safety-research`, `cyber-defense`, `pandemic-preparedness`, `information-integrity`,
`biomedical-rd`. Propose a new area in a
[discussion](../../discussions) if yours does not fit.

**We are looking for contributors.** See [CONTRIBUTING.md](CONTRIBUTING.md) for the
propose → build → review process, and [docs/adding-an-environment.md](docs/adding-an-environment.md)
for the walkthrough.

## Quickstart

```bash
git clone https://github.com/aaygan29/aimpoint.git
cd aimpoint
uv sync
```

```bash
uv run pytest
```

That runs the entire pipeline against a scripted mock model. No API key, no cost, a few
seconds. Then:

```bash
uv run aimpoint list
```

```bash
uv run aimpoint validate
```

```bash
uv run aimpoint run-env --env target_triage --model anthropic/claude-opus-5 --replicates 3
```

Below three replicates the harness refuses to print a headline number. That is deliberate:
a single run reports run-to-run variance as though it were a property of the model.

## The reference environment

[`target_triage`](environments/biomedical_rd/target_triage/) is a retrospective holdout.
The model sees the therapeutic landscape frozen at the start of 2015 and predicts which
biological targets will earn their **first approved drug** for a given disease afterward.
Ground truth is what actually happened: CGRP for migraine, IL-17A and TYK2 for psoriasis,
GIPR for obesity and type 2 diabetes, JAK1 for atopic eczema. 19 positives and 301 known
failures across six diseases, built from ChEMBL's recorded `first_approval` years.

It exists to prove the harness works end to end, and to give the beneficial-capability
proposal something concrete to argue against. Read its
[known limits](environments/biomedical_rd/target_triage/environment.toml) before quoting
any number from it. **It has not been validated as a measure of drug-discovery judgement.**

Baselines on the dev split, which is how you should read any score from it:

| Policy | True score | Proxy score |
| --- | --- | --- |
| `noop` (floor) | 0.000 | 0.000 |
| `always_abstain` | 0.048 | 0.000 |
| `spec_gamer` (adversarial) | 0.195 | **0.458** |
| `prior_art` (reference) | **0.283** | 0.258 |

`spec_gamer` names 400 targets at hedged confidence. It nearly doubles the reference on the
naive metric while scoring below it on the real one. That gap is the specification-gaming
demonstration, and it is something you can run rather than something you have to take on
faith. If a change to the scoring ever lets that policy win, the change broke the
environment, and a test fails.

## Prior art, stated honestly

LLM agents on biomedical target data and on in-silico therapy simulators already exist:
[arXiv 2508.04755](https://arxiv.org/abs/2508.04755),
[DM-Bench](https://arxiv.org/html/2510.00038). They measure task performance. None of them
instrument sycophancy, calibration under pressure, fabrication, or reward hacking. That gap
is what this repo contributes, and we are not claiming more than that.

## Built on

[Inspect](https://inspect.aisi.org.uk/) (UK AI Security Institute) for model abstraction,
concurrency, transcript logging, and the log viewer. Data from
[ChEMBL](https://www.ebi.ac.uk/chembl/) (EMBL-EBI).

## License

Apache-2.0. See [LICENSE](LICENSE).
