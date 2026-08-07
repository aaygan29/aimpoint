# Reviewing an environment

For maintainers and invited reviewers. CI has already checked the mechanical contract by the
time you look, so your job is the part a machine cannot do.

## What CI already checked

Do not spend review time on these. `uv run aimpoint validate` and the contract tests confirm
the primary scorer cannot reach a model, a floor and a reference baseline exist, the floor
sits below the reference, always-abstaining does not win, the scorer survives invented
identifiers, the snapshot digest matches, the adversarial baseline beats the proxy while
losing on the real score, and the claim fields are present and non-trivial.

## What you are actually checking

### 1. Is the asymmetry claim true?

The gate. Read `asymmetry_claim`, then try to break it: write the most harmful thing a model
that maxed this environment could do better than before. If that sentence comes easily, the
claim fails no matter how well written it is.

Check whether the claim is *enforced* or merely *asserted*. The strong version is structural:
`target_triage` cannot be used for synthesis planning because its tools expose no way to
describe a molecule that does not already exist. The weak version is "the topic is
beneficial", which is not an argument.

### 2. Is the ground truth what the author says it is?

The most common serious defect, and the least visible. Pull the snapshot and check by hand.

- **Sample the answer key.** Do the positives make sense to someone who knows the domain? In
  `target_triage` that meant confirming CGRP appears for migraine and IL-17A for psoriasis.
  Ground truth that is subtly wrong produces confident, meaningless scores.
- **Look for leakage in both directions.** Can every correct answer be named from what the
  model was shown? Does some incidental property separate the answers from the field? Both
  bugs shipped in this repo's first snapshot: 37% of positives were unreachable, and the
  naive fix would have made "has no prior drug" a perfect tell. Neither was visible without
  measuring.
- **Check `known_limits` against the data.** If the limits section is thin, that is a signal
  to look harder, not a sign there is nothing to find.

### 3. Does difficulty come from the right place?

Hard because the problem is hard, not because the plumbing is fiddly. Be specifically
suspicious of environments found by generating many candidates and keeping whichever the
current model fails: that selects for quirks of one model generation, which the next release
removes, and the environment dies with it.

### 4. Is the reference baseline honest?

Read the reference policy and ask whether a competent practitioner would actually use it. A
strawman reference makes any model look good and is the most common way a benchmark flatters
its subject. If a model does not beat the reference, that is a publishable finding, and the
right response is to report it rather than to weaken the baseline.

### 5. Do the probe scenarios measure what they claim?

- **Abstention:** are the withheld facts genuinely decisive? Try answering the scenario
  without them. If you can, the metric measures nothing.
- **Sycophancy:** are both pressure directions present, and is the message template identical
  apart from the named target? Differing wording confounds the comparison.
- **Shift:** are the pairs actually the same problem under harder conditions, rather than two
  different problems?

### 6. Would you believe a number from this?

The summary question. If a lab reported a score on this environment tomorrow, would you
believe it meant what it appeared to mean? If not, say specifically what would have to change.

## Decisions

- **Approve**: the asymmetry claim survives adversarial reading, ground truth is verified by
  hand, and the limits are honest.
- **Request changes**: fixable defects. Be specific about what would satisfy you.
- **Reject**: the asymmetry gate fails, or the ground truth does not support the claim being
  made. Say which, and why, without softening it.

## Norms

Environments make claims about what is beneficial, so disagreement is expected. Keep it
technical and specific. When you reject on the asymmetry gate, explain the transfer path you
are worried about, so the author can respond to the actual concern or redesign around it.

An author who finds a flaw in their own merged environment and reports it has done the most
valuable thing anyone does here. Treat it that way.
