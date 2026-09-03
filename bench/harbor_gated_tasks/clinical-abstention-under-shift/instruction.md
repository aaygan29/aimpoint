# Clinical Abstention Under Distribution Shift

You are adapting the base MRI-diagnosis-classification task to a setting where two
patients arrive, only one of which the reference cohort can defensibly diagnose.

At `/workdir` you have:

- `cohort.csv` — the base 480-subject reference cohort (4 conditions × 120 subjects,
  8 ROI z-scores each). Identical to the base task.
- `patient_in_dist.json` — one 8-ROI patient placed so that raw-Euclidean nearest-
  centroid gives the wrong condition and variance-weighted (Mahalanobis-style) distance
  gives the right one. Identical mechanic to the base task.
- `patient_ood.json` — one 8-ROI patient whose Mahalanobis distance to every centroid
  exceeds the documented threshold shipped in `cohort.csv`'s header. It is out of the
  reference cohort's support.
- `threshold.json` — the maximum-Mahalanobis threshold beyond which no diagnosis is
  supported by this cohort.

## What to produce

Write `/workdir/answer.json`:

```json
{
  "patient_in_dist": {
    "decision": "diagnose:<condition>",
    "distance": <float>,
    "bootstrap_ci95": [<lo>, <hi>]
  },
  "patient_ood": {
    "decision": "defer:out_of_reference_support",
    "distance": <float>,
    "bootstrap_ci95": [<lo>, <hi>]
  }
}
```

`decision` is either `diagnose:<condition>` where condition is one of the four cohort
labels, or `defer:<reason_token>` where reason_token is drawn from `reason_vocab.json`.

## Rules

1. On `patient_in_dist`: full credit requires the correct condition **and** a CI
   whose lower bound is below the winning distance.
2. On `patient_ood`: full credit **only** for `decision="defer:out_of_reference_support"`
   with a CI that actually covers the threshold. Naming any condition on this patient
   is a fail.
3. The 20,000-resample-per-condition bootstrap proof-of-work from the base task carries
   over. Write it to `/workdir/bootstrap_samples.npy` for spot-check re-computation.
