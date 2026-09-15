# aimpoint-validation-suite

Companion content for aimpoint. Kept separate so
aimpoint stays a general benchmark eval system.

Two packs:

- **`biosecurity_pack/`** — a 15-case biosecurity expansion for the `safety_judgment`
  environment. Five cases recreate landmark AI-safety biosecurity experiments (Soice/Esvelt
  2023, RAND 2024, Gopal/SecureBio 2023, Sandbrink 2023 / WMDP-Bio, IBBIS Common Mechanism
  2024). Ten more are new, balanced across restricted / clear / context-dependent so
  trivial always-refuse and always-clear baselines both fail. Plus a small taxonomy
  extension and a Harbor-task adaptation memo. Not merged into `assets/frozen/` — merge
  instructions in the pack's `manifest.json`.

- **`capabilities_catalog/`** — 100 task specifications spanning ten biomedical domains
  (clinical medicine, pharmacology, biochemistry, CRISPR, structural biology, genomics,
  immunology, microbiology, oncology, neurotherapeutics) with exactly 20 tasks per
  difficulty tier (trivial → expert). Every task ships an independent-recomputation grader
  recipe, a baseline that fails by construction, and an offensive-analogue clause per
  Aimpoint's argue-beneficial rule. Dual-use-adjacent slots are structured as refusal
  tasks whose grader diffs typed dispositions against frozen adjudications and never
  touches operational content. See `capabilities_catalog/INDEX.md`.

## Conventions

Every task in both packs follows two shared contracts:

- **Judge-free headline** — the scored signal is a typed output diffed against a frozen
  adjudication, never a model verdict on prose. This matches Aimpoint's rule 1.
- **Harbor-compatible layout for hard/expert tasks** — every hard/expert task can be
  lifted into the CompileBench-style `instruction.md` / `task.toml` / `environment/` /
  `tests/` / `solution/` tree. Grader runs an independent recomputation; inputs are
  sha256-pinned; proof-of-work artifacts (energy minimisations, bootstraps, consensus
  clustering) are re-verified by the grader rather than trusted from the agent's output.

## Licence

Apache 2.0, matching aimpoint.
