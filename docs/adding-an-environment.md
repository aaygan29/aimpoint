# Adding an environment

A walkthrough. Read [CONTRIBUTING.md](../CONTRIBUTING.md) first, especially the asymmetry
gate, and open a proposal issue before you build.

## The shape

```
environments/<area>/<your_env>/
├── environment.toml     # metadata, the beneficial-capability case, known limits
├── __init__.py          # exports your env class
├── env.py               # the BeneficialEnv subclass
├── scenarios.py         # scenario construction
├── data.py              # frozen-data access and claim verification
├── assets/              # snapshot + answer key + manifest
├── instruction.md       # the task as a contributor-readable brief
├── README.md            # what it measures and what it does not
└── tests/               # environment-specific tests
```

Directory names must be valid Python identifiers, so `my_env` and not `my-env`. Discovery is
automatic: no registration step, nothing to edit outside your folder.

## 1. Subclass `BeneficialEnv`

Five methods are required.

```python
class MyEnv(BeneficialEnv):
    env_id = "my_env"
    version = "0.1.0"
    summary = "One sentence."
    asymmetry_rationale = "..."  # see CONTRIBUTING.md; 40 words minimum, enforced

    def scenarios(self, split: Split) -> list[Scenario]: ...
    def tools(self, scenario: Scenario) -> list[ToolDef]: ...
    def score_primary(self, scenario, submission) -> PrimaryScore: ...
    def verify_claim(self, scenario, claim: str) -> ClaimVerdict: ...
    def baselines(self) -> list[Baseline]: ...
```

Note what `score_primary` does not receive: a model. That is the type system enforcing rule
one. If you find yourself wanting a judge there, the task is not specified tightly enough
yet; put the judged part in `score_secondary`, which is reported but never in the headline.

Your `tools` supply information gathering only. `submit`, `abstain`, and `request_info` come
from the harness so their semantics are identical everywhere, which is what makes probe
metrics comparable across environments written by different people.

## 2. Declare what your scenarios support

Probes activate from what a `Scenario` declares. You do not implement them.

```python
Scenario(
    id="my_env::case_01",
    split=Split.DEV,
    prompt=brief,
    ground_truth=RankedGroundTruth(positives=..., negatives=...),
    withheld={"eGFR": "24 mL/min"},  # revealed only if the model asks
    decisive_fields=frozenset({"eGFR"}),  # -> abstention probe
    pressure=SycophancyPressure(...),  # -> sycophancy probe
    shift_group="case_01",
    is_shifted=True,  # -> shift probe (needs both members)
)
```

Two things to get right, because they are the usual mistakes:

**Withheld facts must genuinely be decisive.** If the model can answer correctly without
asking, your abstention metric measures nothing. Ask yourself whether *you* could answer
without that fact.

**Sycophancy needs both directions.** Ship scenarios that push toward wrong answers and
toward right ones, using an identical message template with only the named target differing.
If the wording differs between conditions, a model that resists one and yields to the other
tells you nothing except that one message was more persuasive. Without both directions the
harness reports a capitulation rate but withholds `sycophancy_index`, because a model that
never moves is stubborn rather than principled.

## 3. Freeze your data

Eval-time code must never touch a live API. Ship a snapshot, pin it by digest, and provide a
rebuild script.

```python
from aimpoint.core.determinism import canonical_digest, SnapshotSpec
```

Keep the answer key **outside** the digested snapshot directory. The snapshot is exactly
what the model may see; the key is a sibling file. That separation is what lets a held-out
split publish its snapshot while withholding its answers.

Then audit your split. Both of these bugs shipped in this repo's first snapshot and neither
was visible from the outside:

- **Unreachable answers.** If a correct answer cannot be named from what the model was shown,
  you have capped the score below 1.0 and it reads as model incompetence.
- **Separating artifacts.** If some incidental property perfectly identifies the answers,
  you have built a lookup task and it reads as model insight.

`scripts/build_snapshot.py` has a worked `audit()` function that checks both. Copy the
pattern.

## 4. Write baselines

Three roles, and the harness distinguishes them.

```python
Baseline("noop", "Submits nothing.", _noop, role="floor")
Baseline("prior_art", "What a careful analyst would do.", self._heuristic, role="reference")
Baseline("spec_gamer", "Beats the proxy, useless in reality.", self._gamer, role="adversarial")
```

The reference must be genuinely good. A strawman reference makes any model look competent
and is the most common way a benchmark flatters its subject. The adversarial one should beat
your `proxy_score` while losing on `score_primary`; a contract test asserts exactly that, so
if a future scoring change lets the gamer win, CI tells you the environment broke.

## 5. Fill in `environment.toml`

Required, and reviewers read them before your results: `capability_claim`,
`bottleneck_claim`, `asymmetry_claim`, `known_limits`. Each must be a real argument, and CI
rejects anything under 25 words as too short to be one.

`known_limits` is where you say what your ground truth does not mean, where leakage might
remain, and how small your sample is. A thin limits section attracts more scrutiny, not less.

## 6. Validate and test

```bash
uv run aimpoint validate --env my_env
uv run pytest
```

The contract tests run against every discovered environment automatically, so yours is
covered the moment discovery finds it. They check the floor sits below the reference, that
always-abstaining does not win, that the scorer survives identifiers a model invented, and
that your primary scorer cannot reach a model even through a global.

Then a real smoke run:

```bash
uv run aimpoint run-env --env my_env --model anthropic/claude-opus-5 --limit 3 --replicates 1
```

Use `--limit` and one replicate while iterating. For anything you report, use three
replicates or more; below that the harness suppresses the headline on purpose.

## Checklist before opening the PR

- [ ] Proposal issue accepted
- [ ] `uv run aimpoint validate --env my_env` clean
- [ ] `uv run pytest` green
- [ ] `score_primary` reaches no model, and no scorer parses prose
- [ ] Floor, reference, and adversarial baselines all present
- [ ] `proxy_score` implemented, and the gamer beats the proxy while losing on the real score
- [ ] Snapshot digest pinned, answer key outside the snapshot directory
- [ ] Split audited for unreachable answers and separating artifacts
- [ ] `known_limits` states what your ground truth does not mean
- [ ] Asymmetry claim names the offensive analogue and why competence does not transfer
