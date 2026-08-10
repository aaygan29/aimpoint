"""Properties specific to pv_signal_triage that the generic harness contract cannot check.

The shared contract checks that any environment has a floor, a reference, a judge-free
scorer, and a demonstrable proxy gap. It cannot check the two claims this environment makes:
that review burden is scored alongside missed signals rather than behind them, and that a
spurious escalation of a serious event is priced above a spurious escalation of a minor one.
"""

from __future__ import annotations

import pytest

from aimpoint.core.env import ClaimVerdict, Split
from aimpoint.core.protocol import RankedItem, RankedSubmission
from aimpoint.core.registry import load_env

ENV_ID = "pv_signal_triage"


@pytest.fixture(scope="module")
def env():
    return load_env(ENV_ID)


@pytest.fixture(scope="module")
def dev(env):
    return env.scenarios(Split.DEV)


def _oracle(scenario) -> RankedSubmission:
    truth = scenario.ground_truth
    if truth.abstention_is_correct:
        return RankedSubmission(abstained=True, abstention_reason="medicine not on record")
    return RankedSubmission(
        items=[
            RankedItem(id=event, confidence=0.95, supporting_claims=[f"cases_at_least:{event}:15"])
            for event in sorted(truth.positives)
        ]
    )


def _mean(env, dev, policy) -> float:
    return sum(env.score_primary(s, policy(s)).headline for s in dev) / len(dev)


def test_oracle_reaches_the_top_of_the_scale(env, dev):
    """A perfect triage must be able to score 1.0, not be capped by an undefined skill score."""
    assert _mean(env, dev, _oracle) == pytest.approx(1.0, abs=0.01)


def test_escalating_everything_wins_the_usual_metric_and_loses_the_real_one(env, dev):
    """The demonstration, pinned. Recall on real signals cannot see alert fatigue."""
    by_role = {b.role: b for b in env.baselines()}
    gamer, reference = by_role["adversarial"], by_role["reference"]

    def scores(baseline):
        true_v, proxy_v = [], []
        for scenario in dev:
            submission = baseline.policy(scenario)
            true_v.append(env.score_primary(scenario, submission).headline)
            proxy = env.proxy_score(scenario, submission)
            if proxy is not None:
                proxy_v.append(proxy)
        return sum(true_v) / len(true_v), sum(proxy_v) / len(proxy_v)

    gamer_true, gamer_proxy = scores(gamer)
    ref_true, ref_proxy = scores(reference)

    assert gamer_proxy == pytest.approx(1.0), "escalating the whole queue should max out recall"
    assert gamer_proxy > ref_proxy
    assert gamer_true < ref_true, (
        f"escalate_everything scores {gamer_true:.3f} against a reference of {ref_true:.3f}; "
        "the headline is not charging enough for review burden"
    )


def test_a_spurious_serious_escalation_costs_more_than_a_spurious_minor_one(env, dev):
    """The cost-weighting claim, measured rather than asserted.

    Two submissions identical in every way except which false escalation they contain. If
    they score the same, the answer key's cost ratios are not reaching the scorer.
    """
    compared = 0
    for scenario in dev:
        truth = scenario.ground_truth
        if truth.abstention_is_correct:
            continue
        serious = sorted(e for e in truth.negatives if truth.cost_of(e) > 1.0)
        minor = sorted(e for e in truth.negatives if truth.cost_of(e) == 1.0)
        if not serious or not minor:
            continue
        one = RankedSubmission(items=[RankedItem(id=serious[0], confidence=0.9)])
        other = RankedSubmission(items=[RankedItem(id=minor[0], confidence=0.9)])
        serious_restraint = env.score_primary(scenario, one).components["review_restraint"]
        minor_restraint = env.score_primary(scenario, other).components["review_restraint"]
        assert serious_restraint < minor_restraint, (
            f"{scenario.id}: escalating {serious[0]!r} spuriously is priced no higher than "
            f"escalating {minor[0]!r}"
        )
        compared += 1

    assert compared >= 3, "not enough queues mix serious and minor negatives to test the pricing"


def test_review_burden_is_scored_not_just_recall(env, dev):
    """Adding false escalations to a correct answer must lower the score.

    Under a recall-shaped metric this is free. Under this one it must not be.
    """
    for scenario in dev:
        truth = scenario.ground_truth
        if truth.abstention_is_correct or not truth.positives or not truth.negatives:
            continue
        clean = _oracle(scenario)
        padded = RankedSubmission(
            items=[*clean.items]
            + [RankedItem(id=e, confidence=0.5) for e in sorted(truth.negatives)[:5]]
        )
        assert (
            env.score_primary(scenario, padded).headline
            < env.score_primary(scenario, clean).headline
        )


def test_tools_do_not_name_other_drugs(env, dev):
    """Cross-queue lookups must return counts, never identities.

    Naming which other medicines flag an event would let a model identify the withheld drug
    in the shift and abstention variants by matching event profiles, turning both probes into
    retrieval.
    """
    import asyncio

    scenario = next(s for s in dev if s.metadata.get("variant") == "unnamed_drug")
    other_drugs = {d.upper() for d in env._snapshot.drugs} - {scenario.metadata["drug"].upper()}
    event = sorted(env._snapshot.all_events)[0]

    for tool in env.tools(scenario):
        for probe in ("", event, "20"):
            try:
                out = asyncio.run(tool.tool(probe)).upper()
            except (TypeError, ValueError):
                continue
            named = [d for d in other_drugs if d in out]
            assert not named, f"tool {tool.name!r} named other medicines: {named[:3]}"


def test_inventing_an_event_is_fabrication_but_odd_formatting_is_not(env, dev):
    scenario = next(s for s in dev if s.metadata.get("variant") == "base")
    queue = env._snapshot.queues[scenario.metadata["drug"]]
    real = queue.candidates[0]

    assert env.verify_claim(scenario, f"cases_at_least:{real.event}:1") is ClaimVerdict.SUPPORTED
    assert (
        env.verify_claim(scenario, f"cases_at_least:{real.event}:{real.cases_pre + 10_000}")
        is ClaimVerdict.CONTRADICTED
    )
    assert (
        env.verify_claim(scenario, "cases_at_least:NOT A REAL EVENT TERM:20")
        is ClaimVerdict.CONTRADICTED
    )
    assert env.verify_claim(scenario, "this signal looks real to me") is ClaimVerdict.UNVERIFIABLE


def test_every_probe_is_exercised(env, dev):
    covered = {probe for scenario in dev for probe in scenario.probes}
    assert len(covered) == 4, f"only {sorted(p.value for p in covered)} are exercised"


def test_answer_key_is_not_degenerate(env, dev):
    """Both outcomes must be well represented, or the task has no discrimination to make."""
    positives = sum(
        len(s.ground_truth.positives) for s in dev if not s.ground_truth.abstention_is_correct
    )
    negatives = sum(
        len(s.ground_truth.negatives) for s in dev if not s.ground_truth.abstention_is_correct
    )
    base_rate = positives / (positives + negatives)
    assert 0.1 < base_rate < 0.9, f"base rate {base_rate:.3f} leaves nothing to discriminate"
