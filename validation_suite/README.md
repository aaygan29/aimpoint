# validation_suite

Dogfood content for Aimpoint. Not part of the framework — this is the material used to
**test whether the safety-evaluation-making actually works** on Aimpoint's own contract.

Three packs, each self-contained:

- **`biosecurity_pack/`** — a 15-case biosecurity expansion for the `safety_judgment`
  environment. Five cases recreate landmark AI-safety biosecurity experiments (Soice /
  Esvelt 2023, RAND 2024, Gopal / SecureBio 2023, Sandbrink 2023 / WMDP-Bio, IBBIS
  Common Mechanism 2024). Ten more are new, balanced across restricted / clear /
  context-dependent so trivial always-refuse and always-clear baselines both fail. Ships
  a small taxonomy extension and merge instructions. Deliberately not wired into
  `environments/ai_safety/safety_judgment/assets/frozen/` yet, to leave the current
  pinned digest untouched until the merge is reviewed.

- **`capabilities_catalog/`** — 100 task specifications spanning ten biomedical domains
  (clinical medicine, pharmacology, biochemistry, CRISPR, structural biology, genomics,
  immunology, microbiology, oncology, neurotherapeutics), exactly 20 tasks per
  difficulty tier. Every task carries an independent-recomputation grader recipe, a
  baseline that fails by construction, and an offensive-analogue clause per Aimpoint's
  argue-beneficial rule. Dual-use-adjacent slots are refusal tasks whose grader diffs
  typed disposition tokens against a frozen adjudication and never touches operational
  content.

- **`harbor_adaptations/`** — three CompileBench/Harbor-format task directories that
  adapt existing capability tasks into safety-gated siblings (`dual-use-target-triage`,
  `clinical-abstention-under-shift`, `screening-tripwire-clustering`). Each keeps
  Harbor's anti-cheat contract (sha256-pinned inputs, independent grader recomputation,
  proof-of-work re-verified) and adds Aimpoint's judge-free safety signal (typed
  disposition + rationale tokens diffed against a frozen adjudication, never a model
  verdict on prose).

## Why this lives here

The goal is dogfooding: use these packs to confirm that Aimpoint's judge-free scoring,
mandatory baselines, and argue-beneficial rule survive contact with real biosecurity
adjudications and real biomedical capabilities across ten fields and five difficulty
tiers. Keeping it inside the aimpoint repo means the CI that validates
`environments/` can (and should, in a follow-up) also validate that this content plugs
into that same contract without any content changes to the framework itself.

## What is NOT here

Nothing here modifies the shipped `environments/`. The biosecurity pack ships alongside
`safety_judgment` as a merge-ready expansion, not an in-place edit. The Harbor
adaptations reference the base tasks that live at
[harbor-tasks](https://github.com/aaygan29/harbor-tasks) (the standalone repo of
capability tasks) and add safety-gated wrappers only.
