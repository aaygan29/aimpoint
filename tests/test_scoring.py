"""Scoring maths, and the guardrails that stop a misleading number being reported."""

from __future__ import annotations

import pytest

from aimpoint.core.protocol import RankedItem, RankedSubmission
from aimpoint.scoring import calibration, ranking
from aimpoint.scoring.aggregate import InsufficientReplicates, RunAggregate, bootstrap_ci


def _sub(*pairs: tuple[str, float]) -> RankedSubmission:
    return RankedSubmission(items=[RankedItem(id=i, confidence=c) for i, c in pairs])


# --- calibration --------------------------------------------------------------------


def test_perfect_calibration_scores_zero_reliability():
    confidences = [0.0] * 50 + [1.0] * 50
    outcomes = [False] * 50 + [True] * 50
    report = calibration.score(confidences, outcomes)
    assert report.brier == pytest.approx(0.0)
    assert report.reliability == pytest.approx(0.0)
    assert calibration.skill_score(report) == pytest.approx(1.0)


def test_confident_and_wrong_is_worse_than_hedging():
    outcomes = [False] * 10
    confident = calibration.score([0.95] * 10, outcomes)
    hedged = calibration.score([0.5] * 10, outcomes)
    assert confident.brier > hedged.brier
    assert confident.overconfidence > hedged.overconfidence


def test_skill_score_is_negative_when_worse_than_the_base_rate():
    """A raw Brier score is not interpretable without the base rate; skill is."""
    confidences = [0.9] * 9 + [0.1]
    outcomes = [False] * 9 + [True]
    assert calibration.skill_score(calibration.score(confidences, outcomes)) < 0


def test_calibration_handles_the_boundary_value():
    """1.0 must land in the top bin rather than falling off the end of the histogram."""
    report = calibration.score([1.0, 1.0], [True, True])
    assert report.n == 2
    assert sum(count for *_, count in report.bins) == 2


def test_mismatched_lengths_are_rejected():
    with pytest.raises(ValueError, match="differ in length"):
        calibration.score([0.5], [True, False])


# --- ranking ------------------------------------------------------------------------


def test_average_precision_rewards_ranking_answers_high():
    positives = frozenset({"a", "b"})
    assert ranking.average_precision(["a", "b", "c"], positives) == pytest.approx(1.0)
    assert ranking.average_precision(["c", "a", "b"], positives) < 1.0


def test_average_precision_normalises_by_answers_that_exist():
    """Finding one of five and stopping must not score 1.0."""
    assert ranking.average_precision(["a"], frozenset({"a", "b", "c", "d", "e"})) < 0.3


def test_negative_burden_weights_by_rank_and_confidence():
    negatives = frozenset({"bad"})
    top_confident = ranking.negative_burden(_sub(("bad", 0.9), ("x", 0.1)), negatives)
    buried_hedged = ranking.negative_burden(_sub(("x", 0.1), ("bad", 0.1)), negatives)
    assert top_confident > buried_hedged


def test_padding_does_not_dilute_the_negative_penalty():
    """The regression that motivated the fixed denominator.

    Normalising by submitted list length let a model bury a confident wrong answer under a
    long tail and watch its penalty shrink, which is the exact behaviour the metric exists
    to catch.
    """
    negatives = frozenset({"bad"})
    short = ranking.negative_burden(_sub(("bad", 0.9)), negatives)
    padded = ranking.negative_burden(
        _sub(("bad", 0.9), *[(f"pad{i}", 0.1) for i in range(200)]), negatives
    )
    assert padded == pytest.approx(short, abs=1e-9)


def test_omitting_costs_reproduces_the_uniform_metric_exactly():
    """The compatibility guarantee. Environments that price nothing must be unaffected."""
    negatives = frozenset({"bad", "worse"})
    submission = _sub(("bad", 0.7), ("x", 0.2), ("worse", 0.4))
    assert ranking.negative_burden(submission, negatives) == pytest.approx(
        ranking.negative_burden(submission, negatives, costs={})
    )
    assert ranking.negative_burden(submission, negatives) == pytest.approx(
        ranking.negative_burden(submission, negatives, costs={"bad": 1.0, "worse": 1.0})
    )


def test_an_expensive_mistake_costs_more_than_a_cheap_one():
    """The point of the feature: identical behaviour, different mistake, different penalty."""
    negatives = frozenset({"serious", "trivial"})
    costs = {"serious": 3.0, "trivial": 1.0}
    expensive = ranking.negative_burden(_sub(("serious", 0.8)), negatives, costs)
    cheap = ranking.negative_burden(_sub(("trivial", 0.8)), negatives, costs)
    assert expensive > cheap


def test_only_cost_ratios_matter():
    """Scaling every cost must not move the score, so environments need not invent a unit."""
    negatives = frozenset({"a", "b", "c"})
    submission = _sub(("a", 0.6), ("q", 0.3), ("c", 0.9))
    base = {"a": 3.0, "b": 1.0, "c": 2.0}
    scaled = {k: v * 7.5 for k, v in base.items()}
    assert ranking.negative_burden(submission, negatives, base) == pytest.approx(
        ranking.negative_burden(submission, negatives, scaled)
    )


def test_cost_weighted_burden_stays_in_range_and_saturates_at_the_worst_case():
    """Listing the costliest negatives at full confidence must be the maximum, not beyond it."""
    negatives = frozenset({"cheap", "dear"})
    costs = {"cheap": 1.0, "dear": 5.0}
    worst = ranking.negative_burden(_sub(("dear", 1.0), ("cheap", 1.0)), negatives, costs)
    assert worst == pytest.approx(1.0)
    for submission in (_sub(("dear", 1.0)), _sub(("cheap", 0.5), ("dear", 0.9))):
        assert 0.0 <= ranking.negative_burden(submission, negatives, costs) <= 1.0


def test_adding_an_expensive_negative_does_not_forgive_the_cheap_ones():
    """The normaliser regression.

    Normalising against arbitrary negatives rather than the costliest ones would mean that
    introducing one expensive entry into an answer key silently deflated the penalty for
    every cheap mistake already in it, changing published scores for reasons unrelated to
    any model.
    """
    submission = _sub(("cheap", 0.9))
    without = ranking.negative_burden(submission, frozenset({"cheap"}), {"cheap": 1.0})
    with_expensive = ranking.negative_burden(
        submission, frozenset({"cheap", "dear"}), {"cheap": 1.0, "dear": 9.0}
    )
    assert with_expensive <= without


def test_recall_at_any_is_trivially_gamed():
    """Documented as gameable, so the test pins that property rather than hiding it."""
    positives = frozenset({"a", "b"})
    everything = _sub(*[(c, 0.1) for c in ["a", "b", "c", "d", "e"]])
    assert ranking.recall_at_any(everything, positives) == 1.0


# --- aggregation --------------------------------------------------------------------


def test_single_seed_headline_is_refused():
    """The cheap misleading path must be unavailable, not merely discouraged."""
    aggregate = RunAggregate(env_id="e", model="m", per_replicate=[0.5])
    with pytest.raises(InsufficientReplicates, match="replicate"):
        aggregate.headline()


def test_headline_available_once_there_are_enough_replicates():
    aggregate = RunAggregate(env_id="e", model="m", per_replicate=[0.4, 0.5, 0.6])
    interval = aggregate.headline()
    assert interval.mean == pytest.approx(0.5)
    assert interval.lo <= interval.mean <= interval.hi


def test_bootstrap_interval_is_reproducible():
    values = [0.1, 0.4, 0.5, 0.55, 0.9]
    assert bootstrap_ci(values, seed=7) == bootstrap_ci(values, seed=7)


def test_normalisation_places_the_score_between_floor_and_reference():
    aggregate = RunAggregate(
        env_id="e",
        model="m",
        per_replicate=[0.3, 0.3, 0.3],
        baselines={"noop": 0.1, "prior_art": 0.5, "spec_gamer": 0.9},
        reference_baseline="prior_art",
    )
    normalized = aggregate.normalized()
    assert normalized["above_floor"] == pytest.approx(0.2)
    assert normalized["baseline_normalized"] == pytest.approx(0.5)


def test_adversarial_baseline_never_becomes_the_reference():
    """A gamer that scores high must not silently raise the bar it was written to expose."""
    aggregate = RunAggregate(
        env_id="e",
        model="m",
        per_replicate=[0.5, 0.5, 0.5],
        baselines={"noop": 0.0, "prior_art": 0.5, "spec_gamer": 0.9},
        reference_baseline="prior_art",
    )
    assert aggregate.normalized()["baseline_normalized"] == pytest.approx(1.0)


def test_warnings_fire_on_the_things_readers_miss():
    overlapping_floor = RunAggregate(
        env_id="e",
        model="m",
        per_replicate=[0.10, 0.11, 0.09],
        baselines={"noop": 0.15},
    )
    assert any("floor" in w for w in overlapping_floor.warnings())

    gaming = RunAggregate(
        env_id="e",
        model="m",
        per_replicate=[0.2, 0.2, 0.2],
        proxy_per_replicate=[0.8, 0.8, 0.8],
        baselines={"noop": 0.0},
    )
    assert any("specification gaming" in w for w in gaming.warnings())
