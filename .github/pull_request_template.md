<!--
Environment PRs should reference an accepted proposal issue. If you are fixing the harness
rather than adding an environment, delete the environment section.
-->

## What this changes

<!-- One or two sentences. -->

Proposal issue: #

## Environment checklist

- [ ] `uv run aimpoint validate --env <id>` is clean
- [ ] `uv run pytest` is green
- [ ] `score_primary` reaches no model, and no scorer parses prose
- [ ] Floor, reference, and adversarial baselines are all present
- [ ] `proxy_score` is implemented, and the adversarial baseline beats it while losing on the real score
- [ ] Snapshot digest is pinned; the answer key lives outside the snapshot directory
- [ ] Split audited for unreachable answers **and** for separating artifacts
- [ ] `known_limits` states what the ground truth does not mean

## The asymmetry claim

<!--
Paste your asymmetry_claim, then answer directly:

What is the most harmful thing a model that maxed this environment could do better than
before? If that sentence is easy to write, the gate fails and the environment should be
redesigned rather than argued for.
-->

## Ground truth

<!--
How did you verify the answer key is correct rather than merely well-formed? Hand-sampling
counts and is expected. Say what you checked and what you found.

What leakage did you look for, in both directions? Unreachable answers cap the score and
read as model incompetence; separating artifacts inflate it and read as model insight.
-->

## Baselines

| Policy | Role | True score | Proxy score |
| --- | --- | --- | --- |
| `noop` | floor | | |
| `always_abstain` | floor | | |
| | reference | | |
| | adversarial | | |

## Known limits

<!-- The short version of environment.toml's known_limits. What should a reader not conclude? -->
