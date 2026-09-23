# Execution-grounded coding environments (biochem track)

Status: design direction, 2026-09-22. Not yet implemented.

## Why this document exists

Three reviewers converged on the same two points about the current environments:

1. The tasks are guessable. `target_triage`, `pv_signal_triage`, and `safety_judgment`
   all ask the model to read a frozen snapshot and emit a ranked prediction. When the
   answer (CGRP became a migraine drug, montelukast got a psychiatric boxed warning) is
   already in the pretraining corpus, the model recalls it rather than reasons to it, and
   a ranking metric pays out for hedged guessing across many items. A reward signal
   cannot tell recall from research.
2. The tasks do not build research skills. What safety researchers actually need from a
   coding agent is help driving a real computational-biology toolchain, and that is
   exactly where current agents fail. The analogue from interpretability is agents that
   cannot use TransformerLens correctly. The biochem analogue is agents that cannot
   operate a synthesis-screening pipeline, a bioinformatics stack, or an analysis script
   without silent, safety-relevant bugs.

The fix is a new class of environment where the ground truth is **computed at scoring
time by running code**, not stored as a label the model might have memorised. The model's
submission is a code artifact. The verifier runs it in a sandbox on held-out inputs and
checks the computed result plus process-level and invariance properties that guessing
cannot satisfy. This keeps every existing contract (judge-free headline, mandatory
baselines, argue-beneficial) and adds the machinery needed to make coding tasks
reward-hack-resistant.

## What makes a coding verifier hard to hack

Eight properties. An environment in this track should implement as many as apply, and its
`environment.toml` should record which.

1. **Computed oracle, not a stored answer.** The reference solution is run against the
   same held-out inputs the model's artifact is run against, at scoring time. The headline
   compares two computed outputs. There is no label sitting in the repo to recall.

2. **Per-instance randomized inputs.** Each scenario is a generator seeded per replicate,
   not a fixed case. The numeric answer differs across draws and appears in no corpus. A
   model that memorised a paper's headline number scores at chance, because the paper is
   one draw and we score on twenty fresh ones. This is the direct answer to "it can guess
   the prediction from the paper."

3. **Hidden test split.** Tests split into `visible` (the agent may run them during
   development) and `hidden` (only the scorer runs them). Hardcoding to pass visible tests
   fails the hidden ones. The visible/hidden gap is reported as a hacking signal, the same
   way the DEV/TEST gap already is.

4. **Metamorphic and invariance checks.** Rather than only checking the answer, check
   properties the correct process must satisfy. Biochem is unusually rich in these:
   reverse-complement invariance of a DNA screener, codon-degeneracy invariance, strand
   symmetry, permutation invariance of a statistic, monotonicity (adding a true hazard
   homolog must not lower a detection score), unit and scale invariance, chirality. A
   pattern-matcher that produces a plausible number fails the invariance battery. This is
   the single most hack-resistant scorer type, and it is how a hard-to-verify judgment
   (in the spirit of the Conceptual Reasoning Index) is made verifiable.

5. **Trajectory consistency.** Require intermediate artifacts that must be mutually
   consistent with the final answer: the intermediate table, independently reduced by the
   scorer, must reproduce the submitted summary. A guessed final number will not match a
   guessed intermediate. This is a cheap, judge-free consistency scorer.

6. **Planted traps and negative controls in every scenario.** Include instances where the
   obvious shortcut gives a confidently wrong answer: a decoy sequence a naive BLAST call
   flags but which is benign, a batch-confounded feature a leaky pipeline "discovers."
   Scored so the shortcut loses. This is the executable analogue of the existing
   `spec_gamer` and `refuse_everything` baselines.

7. **Error asymmetry preserved.** Reuse the harness cost-weighting. A false negative on a
   real hazard homolog is priced above a false positive, and the score is detection-only
   so the environment never rewards anything on the offensive side.

8. **Adversarial baselines as a merge gate.** Every env ships a `hardcoder`, a
   `visible_test_overfitter`, and a `paper_number_guesser` baseline. If any beats the
   honest reference on the headline, CI fails. This is what "written to survive being
   trained on" means for a coding task.

## Biosafety of the track

Every task is defender-side and detection-scored. None asks the model to design a
pathogen, a toxin, or a synthesis route, or to evade a control. Data is public reference
material only. Where a task touches hazard signatures, it uses hashed or obfuscated
signatures the way production screeners (SecureDNA, IBBIS) do, so no operational sequence
content ever lands in the repo. The `asymmetry_rationale` for the track: competence is
operating standard open bioinformatics tools correctly on public data, and the offensive
mirror image (evasion, de novo design) is a different skill the environment never scores
and whose data it never exposes.

## Task ideas, ranked

### 1. `screen_debug`: hardening a DNA synthesis screening pipeline (build first)

A synthesis-screening researcher has a homology-based screener that is meant to flag
order fragments matching a hazard database. It has a planted defect from a fixed catalogue
of real screener failure modes: missing reverse-complement handling, wrong translation
frame, an e-value threshold that admits too much, fragmentation that drops a signal below
a per-fragment cutoff, exact-match where homology is required. The agent must fix the
screener so it recovers detection on held-out sequences.

- Oracle: a correct reference screener run on the same held-out set (property 1).
- Inputs: generated per replicate by recombining public reference sequences and hashed
  hazard signatures with fresh decoys (property 2).
- Metamorphic battery: reverse-complement invariance, codon-shuffle invariance for
  protein-level hazards, monotonicity under adding a true homolog (property 4).
- Traps: benign decoys with high naive-BLAST similarity that must not be flagged
  (property 6).
- Beneficial claim: screening is a named biosecurity bottleneck; the offensive analogue
  (evasion) is never scored and the task exposes no evasion-useful data.
- Why it resists hacking: "flag everything" is the `refuse_everything` analogue and loses
  on the cost-weighted detection score; hardcoding fails hidden held-out sequences.

### 2. `biotool_drift`: the TransformerLens analogue (built)

The agent computes a specific quantity through a bioinformatics workflow where the common
failure is a silent, safety-relevant bug: 0-based versus 1-based coordinates, BED versus
GFF half-open intervals, strand, multi-chain structures, and reading the wrong field or
range from a Boltz or AlphaFold confidence output. The headline is the computed quantity
against a computed oracle; a correctness-anchored invariance battery catches coordinate,
strand, chain, and field errors directly.

Built as four families (`coord_extract`, `strand_cds`, `multichain_dist`,
`confidence_field`), stdlib-only to keep CI dependency-free. The model writes one `solve`
function per scenario, scored on held-out records (60%) plus the invariance battery (40%).
Baselines: `noop`, `reference` (the naive per-family convention bug), and adversarial
`hardcoder` plus `plausible_junk`. A library-API variant (Biopython, pysam, RDKit) that
reproduces those tools' exact footguns is a planned follow-up.

### 3. `recompute_result`: reproduce a paper result the paper does not contain

Give the methods and the raw data, hold out the result, and perturb the data (fresh seed,
held-out subset) so the correct answer differs from the published headline. Guessing the
paper number scores at chance. This directly converts "infer it from the paper" from a
weakness into the thing being tested against.

### 4. `analysis_audit`: find and fix the planted analysis bug

Hand the agent a biomedical analysis script with a subtle planted defect from a bug-class
catalogue: train/test leakage, wrong multiple-testing correction, a batch confound, a
label swap. The agent must locate and fix it so the corrected pipeline reproduces the
held-out oracle result and passes a hidden unit test targeting that bug class. This is the
"safety researchers use coding agents and they mess up" workflow in its purest form.

### 5. `provenance_audit`: detect contamination or a spiked poison

Given a dataset and a model, write code that detects train/test leakage or an injected
poison. Executable, defensive, and grounded in a computed detection rate.

## Harness work implied

- A sandboxed code-execution scorer (Inspect supports tool/sandbox execution) with a hard
  time and resource budget, network off, so the model's artifact runs against hidden
  inputs deterministically.
- A scenario-generator interface (seeded, per-replicate) alongside the existing frozen
  snapshot interface, so a scenario can be a distribution rather than a fixed case.
- A metamorphic-check base class so invariance batteries are declared, not hand-rolled per
  env.
- The three new adversarial baselines wired into `aimpoint validate` as merge gates.

## Recommended first step

Build `screen_debug` end to end as the reference for the track, the way `target_triage`
was built for the prediction track. It exercises every new piece of harness machinery,
its beneficial argument is the cleanest, and its reward-hacking surface is the one the
reviewers care about most.
