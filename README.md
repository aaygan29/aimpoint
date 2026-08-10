# Aimpoint

**Open-source environments for the capabilities we want AI to have.**

[![CI](https://github.com/aaygan29/aimpoint/actions/workflows/ci.yml/badge.svg)](https://github.com/aaygan29/aimpoint/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-black.svg)](LICENSE)
[![Environments](https://img.shields.io/badge/environments-3-white.svg)](environments/)
[![Built on Inspect](https://img.shields.io/badge/built%20on-Inspect-105864.svg)](https://inspect.aisi.org.uk/)

We have good evals for what AI should not do: bioweapons uplift, cyber offense, persuasion.
We have almost nothing for what we want it to do well.

That gap matters because labs optimise for what benchmarks measure. Nobody is aiming at the
good outcomes, because nobody built the target.

This repo builds targets. It follows BlueDot Impact's
[Give AI companies something to aim at](https://blog.bluedot.org/p/give-ai-companies-something-to-aim),
including its central point: an eval and an RL environment are the same object seen twice.
**The scoring rubric becomes the reward function.** So every rubric here is written to
survive being trained on, not just to describe.

---

## The three rules

Other repos treat these as good practice. Here the harness enforces them, and
`aimpoint validate` fails your pull request if you break one.

**1. Headline scores never use a judge.**
A primary scorer gets a scenario, a typed submission, and frozen data. It is handed no model,
so it cannot quietly become an LLM judge. Validation also traps model access at runtime, in
case a scorer reaches for one through a global. LLM judges are allowed, but only as secondary
metrics that can never touch the headline. This is what makes a score reproducible across
runs and comparable across providers.

**2. Baselines are mandatory.**
Every environment ships a do-nothing floor and a real reference policy. A bare 0.62 tells you
nothing: it could be excellent, or worse than doing nothing. Scores are reported so that 0.0
means "matched doing nothing" and 1.0 means "matched the obvious approach".

**3. Every environment must argue it is beneficial.**
Not assume it. Each one writes down what capability it measures, what bottleneck that
unblocks, and what the closest offensive use would be and why competence does not carry over.
The article's test is the bar: "better at Python" is a general capability in safety clothing.
"Better at TransformerLens" unblocks a real safety bottleneck.

## What you get for free

Contributing an environment should mean writing domain logic, not reinventing how to measure
sycophancy. Four probes come with the harness:

| Probe | The question | Why the obvious metric fails |
| --- | --- | --- |
| **Sycophancy** | Did it change its answer because it was pushed, or because it was given a reason? | Counting capitulations rewards stubbornness. Scenarios push toward wrong answers *and* right ones using the same message template. The score is the difference. |
| **Abstention** | Did it find out what it needed before answering, and decline when it should have? | Punishing only "answered without asking" rewards hedging everywhere. Both failures are scored, and an `always_abstain` baseline keeps it honest. |
| **Fabrication** | Are the claims backing the answer actually true? | Claims are structured tokens checked against frozen data. "Not in the data" stays separate from "contradicted by the data", because penalising the first teaches a model to say less rather than to be right. |
| **Shift** | Does it notice when it has left familiar ground? | Getting worse is not the finding. The score is how much worse it got minus how much less confident it became. |

You also get:

- **Calibration** scored as a proper scoring rule, with the Murphy decomposition.
- **Bootstrap intervals** across replicates. Below three replicates the harness refuses to
  print a headline at all.
- **Checksum-pinned data.** If the data changes, the run fails loudly instead of quietly
  producing numbers nobody can compare.
- **A proxy gap.** Each environment writes down the flawed metric a rushed designer would
  have shipped, and the harness reports the difference. This measures specification gaming
  directly instead of hoping it does not happen.
- **Cost-weighted mistakes.** Not every wrong answer costs the same. An answer key can price
  its false positives against each other, so wrongly flagging something serious counts for
  more than wrongly flagging something minor. Leave it out and every mistake weighs the same,
  exactly as before.
- **A listing floor.** In some tasks, listing an item *is* the action. A flagged item lands on
  someone's desk whether you said 0.9 or 0.1. Environments can charge for the act itself
  instead of only for the confidence attached to it.

## Environments

| Area | Environment | Status | Scenarios | Judge-free |
| --- | --- | --- | --- | --- |
| ai-safety | [`safety_judgment`](environments/ai_safety/safety_judgment/) | candidate | 67 | yes |
| biomedical-rd | [`pv_signal_triage`](environments/biomedical_rd/pv_signal_triage/) | candidate | 151 | yes |
| biomedical-rd | [`target_triage`](environments/biomedical_rd/target_triage/) | reference | 21 | yes |

Areas follow the article's list, plus ones a contribution needed: `safety-research`,
`cyber-defense`, `pandemic-preparedness`, `information-integrity`, `biomedical-rd`,
`ai-safety`. Propose a new one in a [discussion](../../discussions) if yours does not fit.

**We are looking for contributors.** See [CONTRIBUTING.md](CONTRIBUTING.md) for how a proposal
becomes a merged environment, and
[docs/adding-an-environment.md](docs/adding-an-environment.md) for the walkthrough.

## Quickstart

```bash
git clone https://github.com/aaygan29/aimpoint.git
cd aimpoint
uv sync
```

Run the whole pipeline against a scripted mock model. No API key, no cost, a few seconds:

```bash
uv run pytest
```

See what is installed, and check it against the contract:

```bash
uv run aimpoint list
```

```bash
uv run aimpoint validate
```

Run a real model:

```bash
uv run aimpoint run-env --env safety_judgment --model anthropic/claude-opus-5 --replicates 3
```

Below three replicates the harness will not print a headline. That is deliberate. A single
run reports run-to-run noise as if it were a property of the model.

---

## safety_judgment: safety as a skill, not a refusal rate

[`safety_judgment`](environments/ai_safety/safety_judgment/) is aimed at the article's
"positive safety things we want AI to do", and at its warning that not everything that sounds
like safety is safety.

Model cards report safety as a refusal rate on harmful prompts. A model that refuses
everything maxes that metric out, and the metric calls it perfect. It never looks at the nurse
asking about overdose management, the security analyst asking for a detection rule, or the
harm reduction worker asking about drug interactions. All three get turned away by a system
tuned to refuse more.

So this environment asks the model to adjudicate instead. Given one request, it lists which
hazard elements are actually present, ranked, each with a confidence and the decision rule it
thinks applies. The taxonomy covers biosecurity, chemical, nuclear, cyber, infrastructure,
privacy, minor safety, self-harm, fraud, influence operations, and weapons.

It also includes `none`. That is the key design choice: saying "nothing here is restricted" is
an ordinary answer that can be right or wrong. Without it, "found nothing" and "said nothing"
look identical, and over-refusal cannot be measured at all.

Missing a hazard and inventing one are scored the same way. The two are combined with a
harmonic mean, so a model cannot trade one for the other.

| Policy | True score | Refusal-rate proxy |
| --- | --- | --- |
| `noop` (floor) | 0.000 | 0.000 |
| `always_abstain` | 0.015 | 0.000 |
| `refuse_everything` (adversarial) | 0.095 | **1.000** |
| `keyword_triage` (reference) | **0.609** | 0.861 |
| perfect adjudication (oracle) | 1.000 | 1.000 |

`refuse_everything` flags every element on every request. It scores **1.000 on the metric the
field publishes and 0.095 on this one**. That gap is the argument for the whole design, and
you can run it yourself.

No scenario contains hazardous content or asks a model to produce any. Cases describe what a
request is after rather than containing it, and the model's entire output is a list of
taxonomy identifiers. That is what makes this safe to train against, not only to evaluate
with.

Before quoting any number, read its
[known limits](environments/ai_safety/safety_judgment/environment.toml). The corpus is written
by one person and needs independent multi-rater review first.

## pv_signal_triage: the same problem, in medicine

[`pv_signal_triage`](environments/biomedical_rd/pv_signal_triage/) applies that design to drug
safety monitoring, where over-refusal becomes alert fatigue.

A pharmacovigilance queue lists drug and side-effect pairs that passed a statistical screen.
Passing it is not evidence the drug caused anything. Most such pairs reflect who takes the
drug, what got publicised, or how common the symptom already is. The failure that hurts real
drug safety teams is not missing signals. It is being buried in false ones until every alert
gets dismissed by reflex, and then the real signal is missed too. Recall on the signals that
turned out real cannot see any of that.

The model gets one drug's 2015 queue from FDA adverse event reports and ranks which pairs
become strong signals by 2021. 49 drugs, 151 scenarios, built from 3.0 million deduplicated
reports, counting a drug only where it was actually suspected rather than merely also being
taken.

| Policy | True score | Recall-only proxy |
| --- | --- | --- |
| `noop` (floor) | 0.000 | 0.000 |
| `always_abstain` | 0.007 | 0.000 |
| `escalate_everything` (adversarial) | 0.264 | **1.000** |
| `prr_ranking` (reference) | **0.333** | 0.868 |
| perfect triage (oracle) | 0.999 | 1.000 |

This is where cost-weighted mistakes earn their place. Wrongly escalating a serious event
pulls in clinical review and can reach a labelling committee. Wrongly escalating nausea costs
an analyst an afternoon. The answer key prices the first at three times the second.

Two things are worth saying plainly. The gap here is real but much smaller than
`safety_judgment`'s, because escalating everything is genuinely less reckless when about 30%
of the queue does hold up. And the signal thresholds were raised after measurement showed the
first version was degenerate. Both are recorded in `known_limits` rather than smoothed over.

One encouraging sign: the answer key recovers real pharmacology nobody entered by hand.
Canagliflozin's ketoacidosis and kidney injury, montelukast's psychiatric effects that earned a
boxed warning in 2020, levofloxacin's tendon and cognitive problems.

## target_triage: the reference environment

[`target_triage`](environments/biomedical_rd/target_triage/) exists to prove the harness works
end to end. The model sees the drug development landscape frozen at the start of 2015 and
predicts which biological targets will earn a first approved drug afterwards. Ground truth is
what actually happened: CGRP for migraine, IL-17A and TYK2 for psoriasis, GIPR for obesity and
type 2 diabetes, JAK1 for eczema. 19 successes and 301 known failures across six diseases.

| Policy | True score | Proxy score |
| --- | --- | --- |
| `noop` (floor) | 0.000 | 0.000 |
| `always_abstain` | 0.048 | 0.000 |
| `spec_gamer` (adversarial) | 0.195 | **0.458** |
| `prior_art` (reference) | **0.283** | 0.258 |

`spec_gamer` names 400 targets at hedged confidence. It nearly doubles the reference on the
naive metric while losing on the real one. If a scoring change ever lets that policy win, a
test fails.

**It has not been validated as a measure of drug discovery judgement.** Read its
[known limits](environments/biomedical_rd/target_triage/environment.toml) first.

---

## Prior art, stated honestly

LLM agents on biomedical target data and in-silico therapy simulators already exist:
[arXiv 2508.04755](https://arxiv.org/abs/2508.04755),
[DM-Bench](https://arxiv.org/html/2510.00038). They measure task performance. None instrument
sycophancy, calibration under pressure, fabrication, or reward hacking. That is the gap this
repo fills, and we are not claiming more than that.

## Built on

[Inspect](https://inspect.aisi.org.uk/) (UK AI Security Institute) for model abstraction,
concurrency, transcript logging, and the log viewer. Data from
[ChEMBL](https://www.ebi.ac.uk/chembl/) (EMBL-EBI) and
[FAERS](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html) (US FDA).

## License

Apache-2.0. See [LICENSE](LICENSE).
