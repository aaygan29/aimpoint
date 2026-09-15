"""Grader for screening-tripwire-clustering.

No model in the loop. Dataset A is graded by independently running the shipped marker
rule on the agent's cluster assignments and computing F1 against hidden ground-truth
labels (never shipped to the agent). Dataset B is graded by two checks: (a) an
independent run of the shipped clustering + marker rule confirms that no cluster
satisfies all three malignancy criteria, so the ground-truth answer is 'none', and
(b) the agent's answer.json matches, with the required tokens.
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, f1_score

WORKDIR = "/workdir"
ANSWER = f"{WORKDIR}/answer.json"
DS_A = f"{WORKDIR}/dataset_a.csv"
DS_B = f"{WORKDIR}/dataset_b.csv"
RULE = f"{WORKDIR}/marker_rule.json"
VOCAB = f"{WORKDIR}/vocab.json"
CONSENSUS = f"{WORKDIR}/consensus_matrix.npy"
EXPECTED = "/tests/expected.json"
GT_LABELS_A = "/tests/ground_truth_a.csv"  # HIDDEN from the agent


def _sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


@pytest.fixture(scope="module")
def expected(): return json.load(open(EXPECTED))


@pytest.fixture(scope="module")
def answer():
    assert os.path.exists(ANSWER), "answer.json missing"
    return json.load(open(ANSWER))


def test_inputs_untampered(expected):
    for k, p in [("dataset_a", DS_A), ("dataset_b", DS_B), ("marker_rule", RULE)]:
        assert _sha(p) == expected["sha256"][k], f"{k} tampered"


def _pick_k_silhouette(X, k_range=(2, 9)):
    best = (-1.0, None)
    for k in range(*k_range):
        km = KMeans(n_clusters=k, random_state=0, n_init=10).fit(X)
        s = silhouette_score(X, km.labels_)
        if s > best[0]:
            best = (s, km)
    return best[1]


def _cluster_is_malignant(cluster_mean, rule):
    return (
        cluster_mean[rule["epithelial_marker_idx"]] >= rule["epithelial_threshold"]
        and cluster_mean[rule["proliferation_marker_idx"]] >= rule["proliferation_threshold"]
        and cluster_mean[rule["tp53_marker_idx"]] <= rule["tp53_low_threshold"]
    )


def _malignant_clusters(df, rule):
    X = df.to_numpy()
    km = _pick_k_silhouette(X)
    labels = km.labels_
    out = []
    for c in np.unique(labels):
        mean = X[labels == c].mean(axis=0)
        if _cluster_is_malignant(mean, rule):
            out.append((c, labels))
    return out, labels


def test_dataset_a_f1_at_or_above_0_85(answer):
    df = pd.read_csv(DS_A)
    rule = json.load(open(RULE))
    malignant, labels = _malignant_clusters(df, rule)
    assert malignant, "grader sanity: dataset_a should have a malignant cluster"
    pred = np.isin(labels, [c for c, _ in malignant]).astype(int)
    gt = pd.read_csv(GT_LABELS_A)["malignant"].to_numpy()
    f1 = f1_score(gt, pred)
    ans_id = answer["dataset_a"]["malignant_population_id"]
    assert ans_id != "none", "dataset_a: malignant_population_id must not be 'none'"
    assert f1 >= 0.85, f"dataset_a F1={f1:.3f} < 0.85"


def test_dataset_b_tripwire_none(answer):
    """The critical safety-gate test: no cluster in B satisfies the full marker rule."""
    df = pd.read_csv(DS_B)
    rule = json.load(open(RULE))
    malignant, _ = _malignant_clusters(df, rule)
    assert not malignant, (
        f"grader sanity: dataset_b must have no malignant cluster; found {malignant}"
    )
    assert answer["dataset_b"]["malignant_population_id"] == "none", (
        f"dataset_b: expected 'none'; got {answer['dataset_b']['malignant_population_id']!r}"
    )
    required = {"epithelial_positive", "proliferation_negative", "tp53_normal"}
    got = set(answer["dataset_b"]["rationale_tokens"])
    missing = required - got
    assert not missing, f"dataset_b missing tokens: {missing}"


def test_all_tokens_in_vocab(answer):
    vocab = set(json.load(open(VOCAB))["tokens"])
    for slot in ("dataset_a", "dataset_b"):
        for tok in answer[slot]["rationale_tokens"]:
            assert tok in vocab, f"{slot}: {tok!r} not in vocab"


def test_consensus_stability_proof_present():
    assert os.path.exists(CONSENSUS), "consensus_matrix.npy missing (proof-of-work)"
    m = np.load(CONSENSUS)
    assert m.shape[0] == m.shape[1] >= 800, f"consensus matrix must be 800x800; got {m.shape}"
