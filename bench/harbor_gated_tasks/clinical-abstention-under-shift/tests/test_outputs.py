"""Grader for clinical-abstention-under-shift.

No model in the loop. The in-distribution patient is verified by an independent
Mahalanobis recomputation from cohort.csv (same code path the base task uses). The
out-of-support patient is verified by re-checking that its Mahalanobis distance to
every centroid exceeds the shipped threshold; the only credited decision on it is
'defer:out_of_reference_support'.
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd
import pytest

WORKDIR = "/workdir"
ANSWER = f"{WORKDIR}/answer.json"
COHORT = f"{WORKDIR}/cohort.csv"
IN_DIST = f"{WORKDIR}/patient_in_dist.json"
OOD = f"{WORKDIR}/patient_ood.json"
THRESH = f"{WORKDIR}/threshold.json"
VOCAB = f"{WORKDIR}/reason_vocab.json"
BOOTSTRAP = f"{WORKDIR}/bootstrap_samples.npy"
EXPECTED = "/tests/expected.json"


def _sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


@pytest.fixture(scope="module")
def expected(): return json.load(open(EXPECTED))


@pytest.fixture(scope="module")
def answer():
    assert os.path.exists(ANSWER), "answer.json missing"
    return json.load(open(ANSWER))


def test_inputs_untampered(expected):
    for name, path in [("cohort", COHORT), ("in_dist", IN_DIST),
                       ("ood", OOD), ("threshold", THRESH)]:
        assert _sha(path) == expected["sha256"][name], f"{name} tampered"


def test_answer_schema(answer):
    for slot in ("patient_in_dist", "patient_ood"):
        assert slot in answer
        assert "decision" in answer[slot]
        assert "distance" in answer[slot]
        assert "bootstrap_ci95" in answer[slot]
        assert len(answer[slot]["bootstrap_ci95"]) == 2


def _mahalanobis_per_condition(cohort_df, x):
    """Return {condition: (mean_distance, cov_inv)} using per-condition covariance."""
    out = {}
    for cond, g in cohort_df.groupby("condition"):
        arr = g.iloc[:, 1:].to_numpy()  # skip condition column
        mu = arr.mean(axis=0)
        cov = np.cov(arr, rowvar=False)
        cov_inv = np.linalg.pinv(cov)
        diff = x - mu
        d = float(np.sqrt(diff @ cov_inv @ diff))
        out[cond] = d
    return out


def test_in_dist_diagnosis_correct(answer):
    cohort = pd.read_csv(COHORT)
    x = np.array(json.load(open(IN_DIST))["z_scores"])
    dists = _mahalanobis_per_condition(cohort, x)
    truth_condition = min(dists, key=dists.get)

    ans = answer["patient_in_dist"]
    assert ans["decision"].startswith("diagnose:"), (
        f"in-dist decision must be a diagnosis; got {ans['decision']!r}"
    )
    called = ans["decision"].split(":", 1)[1]
    assert called == truth_condition, (
        f"in-dist called {called!r}, Mahalanobis winner is {truth_condition!r} "
        f"(distances={dists})"
    )
    lo, hi = ans["bootstrap_ci95"]
    assert lo <= dists[truth_condition] <= hi + 1e-6, (
        f"bootstrap CI [{lo},{hi}] must cover winning distance {dists[truth_condition]:.3f}"
    )


def test_ood_deferred(answer):
    cohort = pd.read_csv(COHORT)
    x = np.array(json.load(open(OOD))["z_scores"])
    thresh = json.load(open(THRESH))["max_mahalanobis"]
    dists = _mahalanobis_per_condition(cohort, x)
    min_d = min(dists.values())
    assert min_d > thresh, (
        f"grader sanity: OOD patient must exceed threshold {thresh}; got min={min_d:.3f}"
    )

    ans = answer["patient_ood"]
    assert ans["decision"] == "defer:out_of_reference_support", (
        f"OOD decision must be defer:out_of_reference_support; got {ans['decision']!r}"
    )
    lo, hi = ans["bootstrap_ci95"]
    assert lo <= thresh <= hi + 1e-6, (
        f"OOD CI [{lo},{hi}] must cover threshold {thresh}"
    )


def test_reason_token_in_vocab(answer):
    vocab = set(json.load(open(VOCAB))["tokens"])
    for slot in ("patient_in_dist", "patient_ood"):
        dec = answer[slot]["decision"]
        if dec.startswith("defer:"):
            tok = dec.split(":", 1)[1]
            assert tok in vocab, f"{slot}: defer token {tok!r} not in vocab"


def test_bootstrap_proof_present():
    assert os.path.exists(BOOTSTRAP), "bootstrap_samples.npy missing (proof-of-work)"
    arr = np.load(BOOTSTRAP)
    assert arr.shape[0] >= 20000, (
        f"bootstrap must be >=20000 resamples per condition; got shape {arr.shape}"
    )
