# Aimpoint

**Open-source environments for the capabilities we want AI to have.**

[![CI](https://github.com/aaygan29/aimpoint/actions/workflows/ci.yml/badge.svg)](https://github.com/aaygan29/aimpoint/actions/workflows/ci.yml)
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
| ai-safety | [`safety_judgment`](environments/ai_safety/safety_judgment/) | candidate | 67 | yes |
| biomedical-rd | [`pv_signal_triage`](environments/biomedical_rd/pv_signal_triage/) | candidate | 151 | yes |

Areas follow the article's list, extended where a contribution needed a home:
`safety-research`, `cyber-defense`, `pandemic-preparedness`, `information-integrity`,
`biomedical-rd`, `ai-safety`. Propose a new area in a
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

## safety_judgment: measuring safety as a capability, not as a refusal rate

[`safety_judgment`](environments/ai_safety/safety_judgment/) is the first environment aimed
squarely at the article's "positive safety things we want AI to do", and at its warning that
not everything safety-flavoured is safety.

Model cards report safety as a refusal rate on harmful prompts. That metric is maximised by a
model that refuses everything, and it reports that model as perfect. It never looks at the
nurse asking about overdose management, the SOC analyst asking for a detection rule, or the
harm reduction worker asking about drug interactions, all of whom get declined by a system
tuned to raise its refusal rate.

So the model adjudicates instead. Given one request, it submits a ranked shortlist of hazard
elements actually present, each with a confidence and each justified by the decision rule it
believes governs. The taxonomy spans biosecurity, chemical, nuclear, cyber, critical
infrastructure, privacy, minor safety, self-harm, fraud, influence operations, and weapons,
and includes `none`, so clearing a request is an affirmative act that can be right or wrong.

Missing a hazard and inventing one are scored the same way, and the two terms are combined
with a **harmonic mean**, so neither can be traded for the other:

| Policy | True score | Published-style proxy |
| --- | --- | --- |
| `noop` (floor) | 0.000 | 0.000 |
| `always_abstain` | 0.015 | 0.000 |
| `refuse_everything` (adversarial) | 0.095 | **1.000** |
| `keyword_triage` (reference) | **0.609** | 0.861 |
| perfect adjudication (oracle) | 1.000 | 1.000 |

`refuse_everything` flags every element on every request. It scores a **perfect 1.000 on the
metric the field publishes and 0.095 on this one**. That is the whole argument for the design,
and it is a number you can run.

No scenario contains operational hazardous content or asks a model to produce any. Cases
describe what a request seeks rather than containing it, and the output channel is a list of
taxonomy identifiers, which is what makes it safe to train against and not only to evaluate
with. Read its [known limits](environments/ai_safety/safety_judgment/environment.toml) before
quoting any number: the corpus is hand-authored by one person and needs independent
multi-rater adjudication first.

## pv_signal_triage: the same pathology, in medicine

[`pv_signal_triage`](environments/biomedical_rd/pv_signal_triage/) applies the
`safety_judgment` design to pharmacovigilance, where the equivalent of over-refusal is alert
fatigue.

A signal queue is a list of drug/event pairs that cleared a statistical screen. Clearing it is
not evidence of a drug effect: most disproportionate pairs reflect confounding by indication,
publicity driving reporting, or the background frequency of a common term. The failure that
degrades real pharmacovigilance is not missing signals, it is drowning in false ones until the
alerts get overridden by default, at which point the real signal is missed too. The metric
these systems are defended with, recall on the signals that turned out real, cannot see that.

The model receives one drug's 2015 queue from FAERS and ranks which pairs become strong
signals by 2021. 49 drugs, 151 scenarios, built from 3.0M deduplicated reports counting only
primary and secondary suspect drugs.

| Policy | True score | Recall-only proxy |
| --- | --- | --- |
| `noop` (floor) | 0.000 | 0.000 |
| `escalate_everything` (adversarial) | 0.264 | **1.000** |
| `prr_ranking` (reference) | **0.333** | 0.868 |
| perfect triage (oracle) | 0.999 | 1.000 |

The gap is real but smaller than `safety_judgment`'s, because escalating everything is
genuinely less catastrophic when 30% of the queue does hold up. That is stated in
`known_limits` rather than tuned away, along with the fact that the signal thresholds were
raised after measurement showed the first version was degenerate.

The answer key recovers documented pharmacology it was never told about: canagliflozin's
ketoacidosis and acute kidney injury, montelukast's neuropsychiatric cluster that earned a
boxed warning in 2020, levofloxacin's tendon and cognitive events.

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
