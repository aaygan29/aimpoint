# biotool_drift

**The TransformerLens analogue of the execution track.** Safety-relevant computational biology
runs on standard tooling, and that is where coding agents fail: not on the algorithm, but on
the silent convention bugs that make a bioinformatics workflow return the wrong number with no
error. This environment hands the model one function to write and scores what the code computes
on held-out records.

## Task families

| Family | Failure mode it targets |
| --- | --- |
| `coord_extract` | 0-based vs 1-based and half-open coordinates (GFF vs BED). |
| `strand_cds` | Forgetting to reverse-complement a minus-strand feature before translation. |
| `multichain_dist` | Identifying a residue by resSeq alone, ignoring chain, when numbers collide. |
| `confidence_field` | Reading the wrong field (ptm) or off-by-one range into a per-residue pLDDT array. |

## Why it resists reward hacking

| Guarding property | How it shows up here |
| --- | --- |
| Computed oracle | Answers are produced by running the correct function at scoring time, not stored. |
| Per-instance randomized inputs | Records are generated from each scenario seed; answers are in no corpus and differ across seeds. |
| Hidden test split | The model tests against visible examples; scoring uses held-out records. |
| Correctness-anchored metamorphic battery (40%) | Each family ships invariance pairs (coordinate-convention equivalence, strand mirroring, chain-decoy disambiguation, range/field robustness); a pair passes only when both members are correct, so a constant or wrong-field hack cannot satisfy it. |
| Adversarial baselines as a gate | `hardcoder` (memorises visible, collapses on held-out) and `plausible_junk` (well-formed wrong values); tests assert the correct solution beats both. |

## Baselines

| Policy | Role | What it shows |
| --- | --- | --- |
| `noop` | floor | Returns nothing. |
| `reference` | reference | The naive impl with each family's characteristic bug; imperfect so the visible-accuracy proxy has a gap. |
| `plausible_junk` | adversarial | Well-formed but wrong (e.g. ptm instead of mean pLDDT). |
| `hardcoder` | adversarial | Passes every visible example, collapses on held-out records. |

The correct implementation (`baselines.oracle`, not shipped as a scale baseline because a
perfect policy cannot demonstrate the proxy gap) scores at the top; the tests assert it beats
every policy above.

## Known limits

See [`environment.toml`](environment.toml) `known_limits`: the workflows model the convention
failure modes in stdlib rather than a specific library's API; the sandbox is isolated but not
hardened; families are single-bug; the test split is empty in v0; not validated as a measure of
real bioinformatics-engineering skill.

## Safety

All records are synthetic. The environment holds no biological sequences of interest and no
hazard content, scores agreement with a computed reference only, and exposes nothing useful for
design or evasion. See `asymmetry_claim` in [`environment.toml`](environment.toml).
