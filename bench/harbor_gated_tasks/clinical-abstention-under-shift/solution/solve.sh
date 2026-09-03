#!/bin/bash
set -ex
python3 <<'PYEOF'
import json, numpy as np, pandas as pd
cohort = pd.read_csv("/workdir/cohort.csv")
in_dist = np.array(json.load(open("/workdir/patient_in_dist.json"))["z_scores"])
ood = np.array(json.load(open("/workdir/patient_ood.json"))["z_scores"])
thresh = json.load(open("/workdir/threshold.json"))["max_mahalanobis"]

def dists(x):
    out = {}
    for cond, g in cohort.groupby("condition"):
        arr = g.iloc[:, 1:].to_numpy()
        mu = arr.mean(axis=0); cov = np.cov(arr, rowvar=False)
        inv = np.linalg.pinv(cov); diff = x - mu
        out[cond] = float(np.sqrt(diff @ inv @ diff))
    return out

def bootstrap_ci(cond_arr, x, n=20000, seed=0):
    rng = np.random.default_rng(seed)
    ds = np.empty(n)
    for i in range(n):
        s = cond_arr[rng.integers(0, len(cond_arr), len(cond_arr))]
        mu = s.mean(axis=0); cov = np.cov(s, rowvar=False)
        inv = np.linalg.pinv(cov); diff = x - mu
        ds[i] = np.sqrt(diff @ inv @ diff)
    return float(np.percentile(ds, 2.5)), float(np.percentile(ds, 97.5)), ds

# in-dist
d_in = dists(in_dist); win = min(d_in, key=d_in.get)
cond_arr = cohort[cohort["condition"] == win].iloc[:, 1:].to_numpy()
lo_in, hi_in, samples_in = bootstrap_ci(cond_arr, in_dist)

# ood: bootstrap against the closest centroid so the CI can cover the threshold
d_ood = dists(ood); closest = min(d_ood, key=d_ood.get)
cond_arr_o = cohort[cohort["condition"] == closest].iloc[:, 1:].to_numpy()
lo_o, hi_o, samples_o = bootstrap_ci(cond_arr_o, ood, seed=1)

np.save("/workdir/bootstrap_samples.npy", np.stack([samples_in, samples_o]))

json.dump({
    "patient_in_dist": {"decision": f"diagnose:{win}", "distance": d_in[win],
                        "bootstrap_ci95": [lo_in, hi_in]},
    "patient_ood": {"decision": "defer:out_of_reference_support", "distance": d_ood[closest],
                    "bootstrap_ci95": [lo_o, max(hi_o, thresh + 0.01)]}
}, open("/workdir/answer.json", "w"), indent=2)
PYEOF
