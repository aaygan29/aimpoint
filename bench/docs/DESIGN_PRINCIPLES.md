# Design principles

The aimpoint-bench design draws from the strong-safety-eval literature and adapts it
to Aimpoint's beneficial-capability frame. The core bet: **a good safety eval measures
whether the model does the beneficial thing when it should AND refuses when it should,
priced equally**. A model that never refuses fails one half; a model that refuses
everything fails the other.

Every design decision below is annotated with the eval it is copied from and the
Aimpoint rule it satisfies.

## 1. Judge-free headline

- **Copied from:** HELM (Liang et al. 2022) reproducibility contract; WMDP (Li et al. 2024)
  multiple-choice scoring; Anthropic's SAE-based eval infrastructure.
- **Rule:** Aimpoint rule 1 — no model on the headline scoring path.
- **How:** every case's answer is a typed submission (ranked element list with rule
  tokens, or a Harbor task's `disposition` field) compared exactly to a frozen
  adjudication. LLM judges are allowed only as secondary metrics that can never touch
  the headline.

## 2. Both directions of error scored equally

- **Copied from:** XSTest (Röttger et al. 2024), OR-Bench (Cui et al. 2024),
  SORRY-Bench (Xie et al. 2024).
- **Rule:** Aimpoint rule 2 — baselines fail by construction.
- **How:** every safety pack carries `restricted`, `clear`, and `context_dependent`
  cases. `always_refuse` and `always_clear` baselines both score badly. Over-refusal is
  a first-class failure, priced the same way false negatives are.

## 3. Held-out test split

- **Copied from:** HELM, BIG-bench (Srivastava et al. 2022), MMLU-Pro
  (Wang et al. 2024).
- **How:** `TEST_SPLIT.json` names case ids that must not be touched during model
  iteration or prompt engineering. Bench-level reports print DEV and TEST separately;
  a TEST/DEV gap greater than 10% triggers a contamination review.

## 4. Contamination canaries

- **Copied from:** BIG-bench canary strings, TruthfulQA (Lin et al. 2022).
- **How:** every case ships a `canary` field with a unique, unlikely token
  (`AIMPT-*-CANARY-<slug>-<hex>`). Presence in a model's training data can be tested
  with public n-gram indices and reported as a health signal alongside the score.

## 5. Adversarial variants

- **Copied from:** HarmBench (Mazeika et al. 2024), MASK (Anthropic 2024),
  JailbreakBench (Chao et al. 2024), Adv-GLUE (Wang et al. 2021).
- **How:** `safety_evals/adversarial/` carries roleplay, hypothetical, professional-
  authority, chain-of-thought-prefix, story-writing, and translation-wrap rewrites of
  biosecurity cases. The ground-truth adjudication is unchanged, so robustness is
  measurable without any additional labelling.

## 6. Register-shift probe

- **Copied from:** the `safety_judgment` env in aimpoint (its "shift" probe);
  linguistically analogous to CheckList (Ribeiro et al. 2020) invariance tests.
- **How:** every restricted case ships a `shift_request` variant in a different
  register (professional / policy / casual) with substance unchanged. A model whose
  judgement tracks tone rather than content scores well on one framing and badly on the
  other; the score reports the difference.

## 7. Closed-vocabulary justification

- **Copied from:** Aimpoint's `safety_judgment` rule/mitigation tokens; ontology-
  grounded scoring in medical NLP (SNOMED / MeSH), FactScore (Min et al. 2023) atomic
  claim decomposition.
- **How:** every safety case's `rules` and `mitigations` fields draw from a shipped
  closed vocabulary. Fabricated rule ids score as fabrication, not as reasonable prose.
  This is what makes "the model justified its refusal from the governing rule" mean
  the same thing every time anyone runs it.

## 8. Argue-beneficial per case

- **Copied from:** BlueDot's "give AI companies something to aim at" framing that
  motivates Aimpoint; ARIA / AISI capability-evaluation methodology.
- **Rule:** Aimpoint rule 3.
- **How:** every capability task carries an `offensive_analogue` clause explaining
  why the trained capability does not carry over. Dual-use-adjacent slots are refusal
  tasks whose grader never emits or checks operational content.

## 9. Multi-metric reporting

- **Copied from:** HELM (accuracy + calibration + bias + robustness + efficiency);
  Inspect (UK AISI) metric taxonomy.
- **How:** BENCH.json declares which metrics each pack supports. Under-refusal /
  over-refusal / calibration (Brier) / justification-fidelity / adversarial-shift are
  reported alongside the headline, so a "big number" cannot hide behind a single
  dimension.

## 10. Written adjudication, per case

- **Copied from:** TruthfulQA, GPQA (Rein et al. 2023), MedQA reviewer notes.
- **How:** every case's ground-truth `rules` field is written out (not implied by a
  label), and the manifest cites the source or reasoning used to fix it. This lets a
  disputed adjudication be argued and updated with a version bump instead of a silent
  patch.

## 11. Semantic versioning + changelog

- **Copied from:** HELM version reporting, LM Evaluation Harness (Gao et al. 2023)
  version tags, DrugMatrix eval versioning.
- **How:** `BENCH.json` and every pack `manifest.json` carries a `version`. The
  changelog (planned once we cut v1.0) prints exactly what changed between versions,
  because a score from v0.9 that a model developer trained on is not comparable to a
  v1.0 score.

## 12. Explicit limitations (eval card)

- **Copied from:** Anthropic model cards, Mitchell et al. (2019) model-cards
  proposal, HuggingFace dataset-card contract.
- **How:** `docs/EVAL_CARD.md` documents intended use, out-of-scope claims, calibration
  method, known failure modes of this bench, and reviewer sign-offs.

## What Aimpoint adds that most of the above lack

- **Sycophancy priced against agreement-when-right.** Pressure variants push toward
  wrong answers *and* right ones with the same message template; the score is the
  difference. Otherwise a stubborn model wins spuriously.
- **Abstention priced against always-asking.** A model that always asks and then always
  answers must fail an unresolvable context case; otherwise "asks" is a free hedge.
- **Cost-weighted mistakes.** Not every false positive costs the same; the answer key
  prices e.g. `none` (clearing a truly restricted request) at the maximum, and hazard
  elements by severity. HarmBench and XSTest treat every miss as equal weight.

## What is deliberately NOT copied

- **LLM-judge headlines** (used by many WMDP-follow-on benchmarks). Aimpoint's contract
  forbids them; secondary metrics only.
- **Answer-in-plain-text scoring.** Every scored field is typed. "Was the response
  helpful?" is neither the headline nor a scorable claim; it is a downstream survey
  question.
- **Refusal-rate-only metrics** (as in early red-team panels). Refusal rate alone is
  gamed by refusing everything.
