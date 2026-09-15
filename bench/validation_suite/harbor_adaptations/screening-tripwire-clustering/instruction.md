# Screening-Tripwire Clustering

Two unlabelled single-cell datasets are at `/workdir`. You must cluster each and
identify whether a malignant population is present.

- `dataset_a.csv` — 800 cells × 20 marker genes. Same generation process as the base
  `cancer-cell-identification` task. Contains a true malignant population **and** a
  benign-epithelial confound (epithelial-marker-positive but with normal proliferation
  and TP53).
- `dataset_b.csv` — 800 cells × 20 marker genes. **Contains no malignant population**:
  the only epithelial-positive cluster is the confound (proliferation-negative,
  TP53-normal). An agent that flags "epithelial = cancer" without checking proliferation
  and tumor-suppressor signatures will pick this cluster and fail the tripwire.

The marker rule is unchanged from the base task and shipped in `marker_rule.json`.

## What to produce

Write `/workdir/answer.json`:

```json
{
  "dataset_a": {
    "malignant_population_id": "<cluster_id>",
    "rationale_tokens": ["epithelial_positive", "proliferation_positive", "tp53_low"]
  },
  "dataset_b": {
    "malignant_population_id": "none",
    "rationale_tokens": ["epithelial_positive", "proliferation_negative", "tp53_normal"]
  },
  "consensus_stability_pass": true
}
```

## Rules

1. `dataset_a`: F1 against the shipped hidden ground-truth labels must be >= 0.85.
2. `dataset_b`: full credit only for `malignant_population_id="none"` justified by
   the three proliferation/TP53 tokens. Flagging any cluster is a fail.
3. The 500-resample bootstrap consensus-clustering stability check from the base task
   carries over. Write it to `/workdir/consensus_matrix.npy` for spot-check.
