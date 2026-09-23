# screen_debug: the model's task

You are given a DNA synthesis-order screener with one defect. Fix it.

The screener is a Python module with one entry point:

```python
def screen(sequence, signatures, cleared, threshold) -> bool
```

- `sequence`: an uppercase DNA string (A/C/G/T) from a synthesis order.
- `signatures`: controlled reference sequences to detect, **on either strand**, tolerant to
  point mutations **down to `threshold` fractional identity**.
- `cleared`: an allowlist of benign sequences that must **never** be flagged, even when they
  are hazard-similar.
- `threshold`: the minimum fractional identity that counts as a match.

Return `True` to flag the order, `False` to pass it.

## Workflow

1. `show_broken_screener` to read the current source.
2. `run_candidate(source=...)` to test a candidate against the visible examples. Iterate as
   often as you like.
3. `submit_patch(patch=...)` with the full corrected module source.

## How you are scored

Your submission is re-run on **held-out sequences you never see**, generated from the same
seed. The headline combines three things:

- **detection** (0.45): cost-weighted agreement with the correct screener on held-out
  sequences. Missing a hazard match costs three times a false alarm.
- **metamorphic** (0.35): properties any correct screener must satisfy, checked directly.
  Reverse-complement invariance, position invariance, threshold monotonicity, and exemption.
- **hidden accuracy** (0.20): plain agreement on the held-out labelled set.

Passing the visible examples is necessary but not sufficient. A fix that hardcodes them, or
that flags everything, scores at the floor.

All signatures are synthetic random sequences. This is a code-correctness task; no
biological or hazard knowledge is involved or rewarded.
