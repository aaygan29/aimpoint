"""screen_debug: the execution-track reference environment.

These tests assert the properties the environment advertises: a correct fix wins, every
reward-hacking policy loses, the metamorphic battery catches the injected defect, and the
per-instance generation is deterministic. They complement the parametrized contract tests
in `test_contract.py`, which already exercise this environment through the shared gates.
"""

from __future__ import annotations

import pytest

from aimpoint.core.env import Split
from aimpoint.core.registry import load_env

pytestmark = pytest.mark.usefixtures()


@pytest.fixture(scope="module")
def env():
    return load_env("screen_debug")


@pytest.fixture(scope="module")
def scenarios(env):
    return env.scenarios(Split.DEV)


def _mean(env, scenarios, policy):
    vals = [env.score_primary(s, policy(s)).headline for s in scenarios]
    return sum(vals) / len(vals)


def test_discovers_and_declares_patch_mode(env):
    assert env.env_id == "screen_debug"
    assert env.submission_mode == "patch"


def test_dev_split_is_defects_times_seeds(scenarios):
    from environments.biosecurity.screen_debug.scenarios import DEV_SEEDS
    from environments.biosecurity.screen_debug.screener_reference import DEFECTS

    assert len(scenarios) == len(DEFECTS) * len(DEV_SEEDS)


def test_generation_is_deterministic():
    from environments.biosecurity.screen_debug import data

    a = data.build_signatures(11)
    b = data.build_signatures(11)
    c = data.build_signatures(23)
    assert a == b
    assert a != c
    qa = data.build_queries(11, a, 4, "hidden")
    qb = data.build_queries(11, b, 4, "hidden")
    assert [q.sequence for q in qa] == [q.sequence for q in qb]


def test_oracle_scores_at_the_top(env, scenarios):
    from environments.biosecurity.screen_debug import baselines

    oracle = _mean(env, scenarios, baselines.oracle)
    assert oracle > 0.97, f"the correct screener should score ~1.0, got {oracle:.3f}"


def test_correct_fix_beats_every_other_policy(env, scenarios):
    from environments.biosecurity.screen_debug import baselines

    oracle = _mean(env, scenarios, baselines.oracle)
    for name, policy in [
        ("noop", baselines.noop),
        ("forward_only_fix", baselines.forward_only_fix),
        ("hardcoder", baselines.hardcoder),
        ("flag_everything", baselines.flag_everything),
    ]:
        other = _mean(env, scenarios, policy)
        assert oracle > other, f"oracle ({oracle:.3f}) did not beat {name} ({other:.3f})"


def test_flag_everything_wins_proxy_loses_true(env, scenarios):
    from environments.biosecurity.screen_debug import baselines

    def true_and_proxy(policy):
        true = [env.score_primary(s, policy(s)).headline for s in scenarios]
        proxy = [env.proxy_score(s, policy(s)) for s in scenarios]
        proxy = [p for p in proxy if p is not None]
        return sum(true) / len(true), sum(proxy) / len(proxy)

    fa_true, fa_proxy = true_and_proxy(baselines.flag_everything)
    ref_true, ref_proxy = true_and_proxy(baselines.forward_only_fix)

    assert fa_proxy > ref_proxy, "flag_everything must beat the reference on the recall proxy"
    assert fa_true < ref_true, "flag_everything must lose to the reference on the true score"


def test_hardcoder_passes_visible_but_fails_hidden(env, scenarios):
    """The visible/hidden gap: the hack that clears the examples collapses on held-out data."""
    from environments.biosecurity.screen_debug import baselines, data

    scenario = scenarios[0]
    seed = scenario.metadata["seed"]
    sigs = data.build_signatures(seed)
    source = baselines.hardcoder(scenario).patch

    visible = data.build_queries(seed, sigs, baselines.VISIBLE_PER_CATEGORY, baselines.VISIBLE_STREAM)
    vis_out = data.run_candidate(source, [q.sequence for q in visible], sigs)
    vis_pass = sum(o == q.label for q, o in zip(visible, vis_out)) / len(visible)

    headline = env.score_primary(scenario, baselines.hardcoder(scenario)).headline
    assert vis_pass == 1.0, "hardcoder should pass every visible example"
    assert headline < 0.4, f"hardcoder should collapse on held-out data, got {headline:.3f}"


def test_metamorphic_catches_the_injected_defect(env, scenarios):
    """For each defect, the broken source fails at least one invariant the fix restores."""
    from environments.biosecurity.screen_debug import baselines

    seen = set()
    for scenario in scenarios:
        defect = scenario.metadata["defect"]
        if defect in seen:
            continue
        seen.add(defect)
        broken = env.score_primary(scenario, baselines.noop(scenario))
        fixed = env.score_primary(scenario, baselines.oracle(scenario))
        assert broken.components["metamorphic"] < fixed.components["metamorphic"], (
            f"defect {defect} did not lower the metamorphic score below the fix"
        )


def test_ranked_submission_scores_at_floor_without_executing(env, scenarios):
    """The validate probe path: a non-patch submission must not run code and must score 0."""
    from aimpoint.core.protocol import RankedItem, RankedSubmission

    probe = RankedSubmission(items=[RankedItem(id="x", confidence=0.5)])
    score = env.score_primary(scenarios[0], probe)
    assert score.headline == 0.0


def test_empty_and_broken_submissions_do_not_raise(env, scenarios):
    from aimpoint.core.protocol import PatchSubmission

    for patch in ["", "def not_screen(): pass", "syntax error ("]:
        score = env.score_primary(scenarios[0], PatchSubmission(patch=patch))
        assert 0.0 <= score.headline <= 1.0
