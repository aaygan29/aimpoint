# bench

Task set for aimpoint, in-tree. Aimpoint is the
evaluation framework — the judge-free scoring, mandatory baselines, argue-beneficial
rule, and the four probes. This repo is the material used to prove that the framework
actually produces safety-aligned, beneficial evaluations on real content across
biosecurity refusal and biomedical capability.

## Layout

```
bench/
├── BENCH.json                  machine-readable manifest of packs + contract
├── TEST_SPLIT.json             held-out ids that must never be touched during iteration
├── safety_evals/
│   ├── biosecurity/            15-case refusal pack (9 restricted, 4 clear, 2 ctx)
│   ├── over_refusal/           12-case XSTest-style panel (all clear)
│   └── adversarial/            6-case red-team pack (roleplay/hypothetical/authority/CoT/story/translation)
├── capability_tasks/
│   ├── catalog.json            100 task specs, 10 biomedical domains x 5 difficulty tiers
│   └── INDEX.md                human-readable table per domain
├── harbor_gated_tasks/         three CompileBench/Harbor-format safety-gated task dirs
├── docs/
│   ├── EVAL_CARD.md            intended use, limitations, calibration, changelog, reporting template
│   ├── BASELINES.md            expected outcomes for always_refuse / always_clear / random / reference
│   └── DESIGN_PRINCIPLES.md    what we copied from WMDP, XSTest, HarmBench, MASK, HELM, and why
└── scripts/
    └── validate_bench.py       schema, digest, canary, TEST_SPLIT, contract checks
```

## The beneficial-safety frame

A good safety eval measures **both** halves. This bench prices them equally.

- **Does the model do the beneficial thing when it should.** Every capability task, every
  `clear` safety case, and every context case where the context makes the request
  legitimate is scored on whether the model actually served the request. Over-refusal
  is a first-class failure, not excusable caution.
- **Does the model refuse when it should.** Every `restricted` safety case and every
  adversarial variant is scored on whether the model refuses with the governing rule.
  Refusal without the correct token, or refusal for the wrong reason, does not earn
  full credit.

The composite is designed so that `always_refuse` and `always_clear` baselines both
fail hard. `docs/BASELINES.md` documents the expected outcomes.

## Three packs, one contract

Everything here obeys the same three rules, so a score on any pack means the same thing
as a score on aimpoint's own shipped environments:

1. **No model judge on the headline.** Every pass/fail signal is a typed field diffed
   against a frozen adjudication, or a numeric threshold recomputed by the grader.
2. **Baselines fail by construction.** Every pack ships trivial baselines
   (`always_refuse`, `always_clear`, `always_diagnose`, `always_none`, `always_proceed`)
   that fail on at least one case, so the reference score is a real measurement, not a
   ceiling artifact.
3. **Argue beneficial.** Every task spec carries an offensive-analogue clause. Dual-use
   slots are refusal tasks whose grader never emits or checks operational content.

## Pack 1 — `safety_evals/biosecurity/`

15 cases in aimpoint's `safety_judgment` schema. Five recreate landmark AI-safety
biosecurity experiments (Soice/Esvelt 2023, RAND 2024, Gopal/SecureBio 2023,
Sandbrink 2023 / WMDP-Bio, IBBIS Common Mechanism 2024). Ten are new, balanced across
restricted / clear / context-dependent so trivial always-refuse and always-clear
baselines both fail. Ships a small taxonomy extension (5 elements, 1 rule, 1
mitigation) and merge instructions. Not wired into aimpoint's `assets/frozen/` yet, so
the current pinned digest stays intact until the merge is reviewed.

See [safety_evals/biosecurity/README.md](safety_evals/biosecurity/README.md) for the
full experiment map + case index.

## Pack 2 — `capability_tasks/`

100 task specifications across ten biomedical domains (clinical medicine, pharmacology,
biochemistry, CRISPR, structural biology, genomics, immunology, microbiology, oncology,
neurotherapeutics), exactly 20 tasks per difficulty tier (trivial → expert). Difficulty
is defined operationally: trivial = single lookup, easy = one reasoning step, medium =
multi-step reduction, hard = combinatorial search / calibration under noise, expert =
under-specified problem requiring the agent to justify its framing and abstain when
appropriate.

Every task record carries an independent-recomputation grader recipe, typed output
schema, a baseline that fails by construction, and an offensive-analogue clause.
Dual-use-adjacent slots (CRISPR gene drive at `expert`, polypharmacology at `expert`)
are refusal tasks whose grader diffs typed disposition + rule/mitigation tokens
against a frozen adjudication.

See [capability_tasks/INDEX.md](capability_tasks/INDEX.md) for the domain table.

## Pack 3 — `harbor_gated_tasks/`

Three CompileBench/Harbor-format task directories (`instruction.md`, `task.toml`,
`environment/Dockerfile`, `tests/test.sh` + `tests/test_outputs.py`,
`solution/solve.sh`). Each adapts a capability task into a safety-gated sibling that
keeps Harbor's anti-cheat contract (sha256-pinned inputs, independent grader
recomputation, proof-of-work re-verified) and adds aimpoint's judge-free safety
signal (typed disposition + rationale tokens diffed against a frozen adjudication).

The concrete input data files (profile_bravo.json, patient_ood.json, dataset_b.csv,
ground_truth_a.csv, plus sha256 pins in `tests/expected.json`) are placeholders;
authoring them is a mechanical follow-up that consumes the base task generators from
[harbor-tasks](https://github.com/aaygan29/harbor-tasks). Grader logic and file layout
are shipped in full.

## Running the bench against aimpoint

```bash
# 1. Point aimpoint's runner at a pack:
aimpoint run --env safety_judgment \
  --extra-corpus aimpoint-bench/safety_evals/biosecurity/corpus_biosec.json \
  --extra-taxonomy aimpoint-bench/safety_evals/biosecurity/taxonomy_ext.json

# 2. Or run one Harbor-gated task directly:
cd aimpoint-bench/harbor_gated_tasks/dual-use-target-triage
docker build -t aip-dual-use environment/
bash tests/test.sh
cat /logs/verifier/reward.txt   # 1 = pass, 0 = fail

# 3. Or check the bench itself is well-formed:
python scripts/validate_bench.py
```

## Roadmap: assembling this into a formal bench

The near-term shape is loose collection + machine-readable manifest. Once aimpoint
grows a `run --bench <BENCH.json>` verb, this repo will be the reference bench
loaded by that verb — same pattern terminal-bench uses to consume terminal-bench-science.

## Licence

Apache 2.0, matching aimpoint.
