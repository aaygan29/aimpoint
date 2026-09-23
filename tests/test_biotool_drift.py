"""biotool_drift: the second execution-track environment.

Asserts the advertised properties per family: the correct solution wins, reward-hacks lose,
the invariance battery catches the convention bug, and generation is deterministic. The
shared contract tests in test_contract.py exercise it through the common gates too.
"""

from __future__ import annotations

import pytest

from aimpoint.core.env import Split
from aimpoint.core.registry import load_env


@pytest.fixture(scope="module")
def env():
    return load_env("biotool_drift")


@pytest.fixture(scope="module")
def scenarios(env):
    return env.scenarios(Split.DEV)


def _mean(env, scenarios, policy):
    return sum(env.score_primary(s, policy(s)).headline for s in scenarios) / len(scenarios)


def test_declares_patch_mode_and_families(env):
    from environments.biosecurity.biotool_drift.families import FAMILIES

    assert env.submission_mode == "patch"
    assert set(FAMILIES) == {"coord_extract", "strand_cds", "multichain_dist", "confidence_field"}


def test_dev_split_is_families_times_seeds(scenarios):
    from environments.biosecurity.biotool_drift.families import FAMILIES
    from environments.biosecurity.biotool_drift.scenarios import DEV_SEEDS

    assert len(scenarios) == len(FAMILIES) * len(DEV_SEEDS)


def test_generation_is_deterministic():
    from environments.biosecurity.biotool_drift.families import FAMILIES

    fam = FAMILIES["coord_extract"]
    assert fam.generate(7, 5) == fam.generate(7, 5)
    assert fam.generate(7, 5) != fam.generate(19, 5)


def test_oracle_source_matches_python_oracle():
    """The oracle module string and the in-process oracle must agree, or ground truth and the
    shipped correct answer diverge."""
    from environments.biosecurity.biotool_drift import common
    from environments.biosecurity.biotool_drift.families import FAMILIES

    for fam in FAMILIES.values():
        recs = fam.generate(7, 20)
        outs = common.run_solve(fam.ORACLE_SOURCE, recs)
        assert all(o == fam.oracle(r) for r, o in zip(recs, outs, strict=False)), fam.FAMILY_ID


def test_oracle_scores_at_the_top(env, scenarios):
    from environments.biosecurity.biotool_drift import baselines

    assert _mean(env, scenarios, baselines.oracle) > 0.97


def test_correct_solution_beats_every_other_policy(env, scenarios):
    from environments.biosecurity.biotool_drift import baselines

    oracle = _mean(env, scenarios, baselines.oracle)
    for name, policy in [
        ("noop", baselines.noop),
        ("reference", baselines.reference),
        ("plausible_junk", baselines.plausible_junk),
        ("hardcoder", baselines.hardcoder),
    ]:
        assert oracle > _mean(env, scenarios, policy), name


def test_reference_beats_floor(env, scenarios):
    from environments.biosecurity.biotool_drift import baselines

    assert _mean(env, scenarios, baselines.reference) > _mean(env, scenarios, baselines.noop) + 0.01


def test_hardcoder_wins_proxy_loses_true(env, scenarios):
    from environments.biosecurity.biotool_drift import baselines

    def true_and_proxy(policy):
        true = [env.score_primary(s, policy(s)).headline for s in scenarios]
        proxy = [env.proxy_score(s, policy(s)) for s in scenarios]
        proxy = [p for p in proxy if p is not None]
        return sum(true) / len(true), sum(proxy) / len(proxy)

    hc_true, hc_proxy = true_and_proxy(baselines.hardcoder)
    ref_true, ref_proxy = true_and_proxy(baselines.reference)

    assert hc_proxy > ref_proxy, "hardcoder must beat the reference on the visible-accuracy proxy"
    assert hc_true < ref_true, "hardcoder must lose to the reference on the true score"


def test_metamorphic_catches_each_family_bug(env, scenarios):
    from environments.biosecurity.biotool_drift import baselines

    seen = set()
    for scenario in scenarios:
        fam = scenario.metadata["family"]
        if fam in seen:
            continue
        seen.add(fam)
        broken = env.score_primary(scenario, baselines.reference(scenario)).components[
            "metamorphic"
        ]
        fixed = env.score_primary(scenario, baselines.oracle(scenario)).components["metamorphic"]
        assert broken < fixed, fam


def test_ranked_submission_scores_at_floor_without_executing(env, scenarios):
    from aimpoint.core.protocol import RankedItem, RankedSubmission

    probe = RankedSubmission(items=[RankedItem(id="x", confidence=0.5)])
    assert env.score_primary(scenarios[0], probe).headline == 0.0


def test_broken_submissions_do_not_raise(env, scenarios):
    from aimpoint.core.protocol import PatchSubmission

    for patch in ["", "def nope(): pass", "syntax ("]:
        score = env.score_primary(scenarios[0], PatchSubmission(patch=patch))
        assert 0.0 <= score.headline <= 1.0
