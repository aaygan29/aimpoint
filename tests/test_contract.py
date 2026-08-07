"""The harness contract: what every environment must satisfy to be mergeable.

These are the tests CI gates merges on. Each corresponds to a way an eval repo becomes
untrustworthy, and each fails loudly rather than degrading quietly.
"""

from __future__ import annotations

import pytest

from aimpoint.core.determinism import ModelCallInScorer, no_model_calls
from aimpoint.core.env import Split
from aimpoint.core.protocol import RankedItem, RankedSubmission
from aimpoint.core.registry import available_envs, discover_manifests, load_env, validate_env

ALL_ENV_IDS = sorted(available_envs())


def test_at_least_one_environment_is_discoverable():
    assert ALL_ENV_IDS, "no environments found; discovery is broken"


@pytest.mark.parametrize("env_id", ALL_ENV_IDS)
def test_environment_satisfies_contract(env_id):
    violations = validate_env(load_env(env_id))
    assert not violations, "\n".join(f"[{v.check}] {v.detail}" for v in violations)


@pytest.mark.parametrize("env_id", ALL_ENV_IDS)
def test_primary_scorer_cannot_reach_a_model(env_id):
    """Judge-freeness, proven by trapping model acquisition rather than by inspection."""
    env = load_env(env_id)
    scenario = env.scenarios(Split.DEV)[0]
    submission = RankedSubmission(items=[RankedItem(id="whatever", confidence=0.5)])

    with no_model_calls():
        env.score_primary(scenario, submission)  # must not raise


def test_no_model_calls_guard_actually_fires():
    """The guard is only worth having if it catches the thing it claims to catch."""
    with pytest.raises(ModelCallInScorer), no_model_calls():
        from inspect_ai.model import get_model

        get_model("mockllm/model")


@pytest.mark.parametrize("env_id", ALL_ENV_IDS)
def test_scorer_tolerates_ids_the_model_invented(env_id):
    """Models hallucinate identifiers. A scorer that crashes on one scores the run at zero
    for the wrong reason and looks like a model failure."""
    env = load_env(env_id)
    for scenario in env.scenarios(Split.DEV):
        submission = RankedSubmission(
            items=[
                RankedItem(id="NOT_A_REAL_ID_12345", confidence=0.9, supporting_claims=["garbage"]),
                RankedItem(id="", confidence=0.0),
            ]
        )
        score = env.score_primary(scenario, submission)
        assert 0.0 <= score.headline <= 1.0


@pytest.mark.parametrize("env_id", ALL_ENV_IDS)
def test_baselines_separate(env_id):
    """A floor that is not the lowest score means the scale is broken."""
    env = load_env(env_id)
    scenarios = env.scenarios(Split.DEV)

    means = {}
    for baseline in env.baselines():
        values = [env.score_primary(s, baseline.policy(s)).headline for s in scenarios]
        means[baseline.name] = sum(values) / len(values)

    reference_names = [b.name for b in env.baselines() if b.role == "reference"]
    best_reference = max(means[n] for n in reference_names)

    assert means["noop"] <= best_reference, (
        f"the no-op floor ({means['noop']:.3f}) is not below the reference "
        f"({best_reference:.3f}); the scale is inverted"
    )
    assert best_reference > means["noop"] + 0.01, (
        "the reference policy barely beats doing nothing, so the environment cannot "
        "distinguish competence from inactivity"
    )


@pytest.mark.parametrize("env_id", ALL_ENV_IDS)
def test_always_abstain_does_not_win(env_id):
    """If refusing to answer scores well, the scenario mix is unbalanced and the abstention
    metric measures nothing."""
    env = load_env(env_id)
    scenarios = env.scenarios(Split.DEV)
    names = {b.name: b for b in env.baselines()}
    if "always_abstain" not in names:
        pytest.skip("environment ships no always_abstain baseline")

    abstain = names["always_abstain"]
    values = [env.score_primary(s, abstain.policy(s)).headline for s in scenarios]
    mean = sum(values) / len(values)
    assert mean < 0.25, (
        f"always-abstain scores {mean:.3f}; too many scenarios reward declining, so the "
        "environment rewards hedging over judgement"
    )


@pytest.mark.parametrize("env_id", ALL_ENV_IDS)
def test_proxy_metric_is_gameable_and_the_gap_shows_it(env_id):
    """The specification-gaming demonstration must actually demonstrate.

    An adversarial baseline should beat the reference on the proxy while losing on the true
    score. If it stops doing so, either the proxy stopped being naive or the true score
    stopped punishing padding, and either way the environment lost the property it advertises.
    """
    env = load_env(env_id)
    scenarios = env.scenarios(Split.DEV)
    by_role = {b.role: b for b in env.baselines()}
    if "adversarial" not in by_role:
        pytest.skip("environment ships no adversarial baseline")

    def means(baseline):
        true_values, proxy_values = [], []
        for scenario in scenarios:
            submission = baseline.policy(scenario)
            true_values.append(env.score_primary(scenario, submission).headline)
            proxy = env.proxy_score(scenario, submission)
            if proxy is not None:
                proxy_values.append(proxy)
        return (
            sum(true_values) / len(true_values),
            sum(proxy_values) / len(proxy_values) if proxy_values else 0.0,
        )

    gamer_true, gamer_proxy = means(by_role["adversarial"])
    ref_true, ref_proxy = means(by_role["reference"])

    assert gamer_proxy > ref_proxy, "the adversarial baseline does not beat the proxy metric"
    assert gamer_true < ref_true, (
        "the adversarial baseline also beats the true metric, so the true metric is gameable"
    )


def test_manifests_declare_the_beneficial_case():
    """Every environment must argue that it is beneficial rather than assume it."""
    for manifest in discover_manifests():
        metadata = manifest.raw.get("metadata", {})
        for field in ("capability_claim", "bottleneck_claim", "asymmetry_claim", "known_limits"):
            value = metadata.get(field, "")
            assert value and len(value.split()) >= 25, (
                f"{manifest.path}: {field} is missing or too short to be an argument"
            )
