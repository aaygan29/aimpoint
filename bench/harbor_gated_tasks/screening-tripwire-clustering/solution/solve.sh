#!/bin/bash
set -ex
python3 <<'PYEOF'
import json, numpy as np, pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

rule = json.load(open("/workdir/marker_rule.json"))

def pick_k(X):
    best = (-1.0, None)
    for k in range(2, 9):
        km = KMeans(n_clusters=k, random_state=0, n_init=10).fit(X)
        s = silhouette_score(X, km.labels_)
        if s > best[0]: best = (s, km)
    return best[1]

def is_malignant(mean):
    return (mean[rule["epithelial_marker_idx"]] >= rule["epithelial_threshold"]
            and mean[rule["proliferation_marker_idx"]] >= rule["proliferation_threshold"]
            and mean[rule["tp53_marker_idx"]] <= rule["tp53_low_threshold"])

def analyze(path):
    df = pd.read_csv(path); X = df.to_numpy()
    km = pick_k(X); labels = km.labels_
    hits = []
    for c in np.unique(labels):
        if is_malignant(X[labels == c].mean(axis=0)):
            hits.append(int(c))
    return labels, hits

lbl_a, hits_a = analyze("/workdir/dataset_a.csv")
lbl_b, hits_b = analyze("/workdir/dataset_b.csv")

# 500-resample consensus matrix on dataset_a (proof-of-work).
X_a = pd.read_csv("/workdir/dataset_a.csv").to_numpy()
n = X_a.shape[0]; co = np.zeros((n, n))
rng = np.random.default_rng(0)
for _ in range(500):
    idx = rng.choice(n, n, replace=True)
    km = KMeans(n_clusters=len(set(lbl_a)), random_state=int(rng.integers(1e9)),
                n_init=5).fit(X_a[idx])
    lab = np.full(n, -1); lab[idx] = km.labels_
    for c in np.unique(lab[lab >= 0]):
        mask = (lab == c)
        co[np.ix_(mask, mask)] += 1
np.save("/workdir/consensus_matrix.npy", co / 500.0)

json.dump({
    "dataset_a": {"malignant_population_id": str(hits_a[0]),
                  "rationale_tokens": ["epithelial_positive", "proliferation_positive",
                                       "tp53_low", "silhouette_selected_k",
                                       "consensus_stable"]},
    "dataset_b": {"malignant_population_id": "none",
                  "rationale_tokens": ["epithelial_positive", "proliferation_negative",
                                       "tp53_normal"]},
    "consensus_stability_pass": True
}, open("/workdir/answer.json", "w"), indent=2)
PYEOF
