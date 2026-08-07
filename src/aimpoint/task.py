"""Adapter from a `BeneficialEnv` to an Inspect task.

Building on Inspect rather than a bespoke runner buys provider abstraction, concurrency,
retries, transcript logging, and the log viewer, none of which are the interesting part of
this project. It also means an environment written here can be run by anyone who already
knows Inspect, which matters more for adoption than any amount of custom tooling.

The scorer is where the harness earns its keep. It computes the judge-free primary score,
runs every applicable probe, and stows the whole breakdown in the score metadata so that
aggregation, the proxy gap, and the probe rollups can all be reconstructed from a log
without re-running anything.
"""

from __future__ import annotations

from inspect_ai import Task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState

from aimpoint.core.env import BeneficialEnv, Scenario, Split
from aimpoint.core.episode import DEFAULT_MAX_TURNS, episode, read_episode
from aimpoint.probes import run_all


def scenario_samples(scenarios: list[Scenario]) -> list[Sample]:
    """Turn scenarios into Inspect samples.

    The prompt is carried in metadata rather than in `input` because the episode solver
    composes the real first message itself, including the protocol instructions. Leaving
    the input as a short marker keeps the log readable.
    """
    return [
        Sample(
            id=scenario.id,
            input=f"[{scenario.id}]",
            metadata={
                "scenario_id": scenario.id,
                "variant": scenario.metadata.get("variant", "base"),
                "disease": scenario.metadata.get("disease"),
            },
        )
        for scenario in scenarios
    ]


@scorer(metrics=[mean(), stderr()])
def aimpoint_scorer(env: BeneficialEnv, scenarios: dict[str, Scenario]) -> Scorer:
    """Score an episode: primary metric, proxy metric, and all applicable probes."""

    async def score(state: TaskState, target: Target) -> Score:
        scenario = scenarios[state.metadata["scenario_id"]]
        record = read_episode(state)

        submission = record.submission
        if submission is None:
            return Score(
                value=0.0,
                explanation="episode ended without a terminal action",
                metadata={"termination": record.termination, "probes": [], "components": {}},
            )

        primary = env.score_primary(scenario, submission)
        proxy = env.proxy_score(scenario, submission)
        probes = run_all(scenario, record, env)

        return Score(
            value=primary.headline,
            answer=",".join(submission.ordered_ids[:10]),
            explanation=primary.notes,
            metadata={
                "components": primary.components,
                "proxy": proxy,
                "termination": record.termination,
                "turns": record.turns,
                "abstained": submission.abstained,
                "variant": scenario.metadata.get("variant", "base"),
                "shift_group": scenario.shift_group,
                "is_shifted": scenario.is_shifted,
                "probes": [p.model_dump(mode="json") for p in probes],
            },
        )

    return score


def build_task(
    env: BeneficialEnv,
    split: Split = Split.DEV,
    max_turns: int = DEFAULT_MAX_TURNS,
    limit: int | None = None,
) -> Task:
    """Build the Inspect task for one environment and split."""
    scenarios = env.scenarios(split)
    if limit is not None:
        scenarios = scenarios[:limit]
    if not scenarios:
        raise ValueError(
            f"{env.env_id} has no scenarios in split {split.value!r}. "
            "The held-out split is intentionally empty in v0."
        )

    by_id = {scenario.id: scenario for scenario in scenarios}
    return Task(
        dataset=scenario_samples(scenarios),
        solver=episode(env, by_id, max_turns=max_turns),
        scorer=aimpoint_scorer(env, by_id),
        name=f"aimpoint_{env.env_id}",
        metadata={"env_id": env.env_id, "env_version": env.version, "split": split.value},
    )


__all__ = ["aimpoint_scorer", "build_task", "scenario_samples"]
