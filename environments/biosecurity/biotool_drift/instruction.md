# biotool_drift: the model's task

Write one bioinformatics function correctly. Each scenario names a task and a strict input
contract; the common way to fail is a silent convention bug, so read the contract carefully.

The four task families:

- **coord_extract**: extract a feature's subsequence, respecting the record's coordinate
  convention (GFF 1-based inclusive vs BED 0-based half-open).
- **strand_cds**: translate a coding feature, reverse-complementing minus-strand features.
- **multichain_dist**: CA-CA distance between two residues identified by *both* chain and
  resSeq (residue numbers repeat across chains).
- **confidence_field**: mean pLDDT over a 1-based inclusive residue range, from the per-residue
  `plddt` array (not the scalar ptm/iptm fields).

## Workflow

1. `show_examples` to see visible records with their expected answers.
2. `run_solve(source=...)` to test a candidate module (`def solve(record): ...`) against them.
3. `submit_patch(patch=...)` with your full module.

## Scoring

Your `solve` is re-run on **held-out records you never see** (60% of the headline) and on an
**invariance battery** (40%) that checks the convention directly: the same feature in both
coordinate conventions must extract the same bases; a feature and its reverse-strand mirror
must translate the same; a residue lookup must ignore a colliding decoy in another chain; a
confidence mean must not depend on the wrong field. Passing the visible examples is necessary
but not sufficient; memorising them scores at the floor.

All records are synthetic. This is a code-correctness task; no biological knowledge is involved.
