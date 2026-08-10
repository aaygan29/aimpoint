"""Running an environment against a model, across replicates, with baselines.

The unit of work is a *run*: one model, one environment, one split, N replicates. N is
never 1 by default, because a single pass reports run-to-run variance as though it were a
property of the model, and the whole point of an environment meant for training is that
its numbers hold still.

Baselines are computed in the same call rather than left as a separate step someone can
skip. They cost nothing (no model is involved) and without them the model's number has no
scale, so there is no reason to make them optional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from inspect_ai import eval as inspect_eval

from aimpoint.core.determinism import derive_seed
from aimpoint.core.env import BeneficialEnv, Split
from aimpoint.core.episode import DEFAULT_MAX_TURNS
from aimpoint.probes import abstention, fabrication, shift, sycophancy
from aimpoint.probes.base import ProbeResult
from aimpoint.scoring.aggregate import RunAggregate
from aimpoint.task import build_task

DEFAULT_REPLICATES = 3


@dataclass
class RunResult:
    """Everything one run produced, ready to be written as a run card."""

    env_id: str
    env_version: str
    model: str
    split: str
    replicates: int
    seed: int
    aggregate: RunAggregate
    probe_metrics: dict[str, float] = field(default_factory=dict)
    shift_metrics: dict[str, float] = field(default_factory=dict)
    per_scenario: list[dict[str, Any]] = field(default_factory=list)
    log_dir: str = ""

    def as_card(self) -> dict[str, Any]:
        """The committed artifact.

        Deliberately includes `warnings` alongside the numbers. A run card that reports a
        score without reporting that its interval overlaps the no-op floor is a run card
        that will be quoted misleadingly, and the fix is to make the caveat as portable as
        the number.
        """
        card: dict[str, Any] = {
            "env_id": self.env_id,
            "env_version": self.env_version,
            "model": self.model,
            "split": self.split,
            "replicates": self.replicates,
            "seed": self.seed,
            "baselines": self.aggregate.baselines,
            "reference_baseline": self.aggregate.reference_baseline,
            "probes": self.probe_metrics,
            "shift": self.shift_metrics,
            "proxy_gap": self.aggregate.proxy_gap(),
            "warnings": self.aggregate.warnings(),
            "log_dir": self.log_dir,
        }
        try:
            interval = self.aggregate.headline()
            card["headline"] = {
                "mean": interval.mean,
                "ci_lo": interval.lo,
                "ci_hi": interval.hi,
                "n": interval.n,
            }
            card["normalized"] = self.aggregate.normalized()
        except Exception as exc:  # headline suppressed on too few replicates
            card["headline"] = None
            card["headline_suppressed"] = str(exc)
        return card


def run_baselines(
    env: BeneficialEnv, split: Split, limit: int | None = None
) -> tuple[dict, str | None]:
    """Score every baseline over the same scenarios the model will see.

    Returns the scores and the name of the baseline that defines the top of the normalised
    scale. Adversarial baselines are scored and reported but never become the reference.
    """
    scenarios = env.scenarios(split)
    if limit is not None:
        scenarios = scenarios[:limit]

    scores: dict[str, float] = {}
    reference: str | None = None
    for baseline in env.baselines():
        values = [
            env.score_primary(scenario, baseline.policy(scenario)).headline
            for scenario in scenarios
        ]
        scores[baseline.name] = sum(values) / len(values) if values else 0.0
        if baseline.role == "reference" and (
            reference is None or scores[baseline.name] > scores[reference]
        ):
            reference = baseline.name
    return scores, reference


def _rollup_probes(per_scenario: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate probe results across every scenario and replicate."""
    by_kind: dict[str, list[ProbeResult]] = {"sycophancy": [], "abstention": [], "fabrication": []}
    for row in per_scenario:
        for raw in row.get("probes", []):
            result = ProbeResult.model_validate(raw)
            by_kind.setdefault(str(result.kind), []).append(result)

    out: dict[str, float] = {}
    out.update(sycophancy.aggregate(by_kind.get("sycophancy", [])))
    out.update(abstention.aggregate(by_kind.get("abstention", [])))
    out.update(fabrication.aggregate(by_kind.get("fabrication", [])))
    return out


def _rollup_shift(per_scenario: list[dict[str, Any]]) -> dict[str, float]:
    """Pair shifted and unshifted scenarios and measure degradation against confidence."""
    observations = []
    for row in per_scenario:
        group = row.get("shift_group")
        if group is None:
            continue
        observations.append(
            shift.ShiftObservation(
                group=f"{group}::rep{row['replicate']}",
                is_shifted=bool(row.get("is_shifted")),
                score=float(row.get("score", 0.0)),
                mean_confidence=float(row.get("mean_confidence", 0.0)),
                abstained=bool(row.get("abstained")),
            )
        )
    return shift.aggregate(observations)


def run(
    env: BeneficialEnv,
    model: str,
    split: Split = Split.DEV,
    replicates: int = DEFAULT_REPLICATES,
    seed: int = 0,
    max_turns: int = DEFAULT_MAX_TURNS,
    limit: int | None = None,
    log_dir: str | None = None,
    **eval_kwargs: Any,
) -> RunResult:
    """Run one model on one environment across replicates, and score everything."""
    task = build_task(env, split=split, max_turns=max_turns, limit=limit)

    per_replicate: list[float] = []
    proxy_per_replicate: list[float] = []
    per_scenario: list[dict[str, Any]] = []
    resolved_log_dir = log_dir or f"logs/{env.env_id}"

    for replicate in range(replicates):
        replicate_seed = derive_seed(seed, env.env_id, model, replicate)
        logs = inspect_eval(
            task,
            model=model,
            log_dir=resolved_log_dir,
            # Generation settings are passed as keyword arguments, not wrapped in a
            # `config=` object. Inspect's `eval()` has no `config` parameter and forwards
            # unknown keywords into `GenerateConfig(**kwargs)`, so `config=GenerateConfig(...)`
            # becomes `GenerateConfig(config=...)` and raises before a single sample runs.
            # That is the whole of `aimpoint run-env` failing on a clean install, and it was
            # invisible because the tests drove `inspect_eval` directly and never this path.
            seed=replicate_seed,
            display="none",
            **eval_kwargs,
        )

        scores: list[float] = []
        proxies: list[float] = []
        for log in logs:
            for sample in log.samples or []:
                score = (sample.scores or {}).get("aimpoint_scorer")
                if score is None:
                    continue
                value = float(score.value) if isinstance(score.value, int | float) else 0.0
                scores.append(value)
                meta = score.metadata or {}
                if meta.get("proxy") is not None:
                    proxies.append(float(meta["proxy"]))
                per_scenario.append(
                    {
                        "replicate": replicate,
                        "scenario_id": str(sample.id),
                        "score": value,
                        "variant": meta.get("variant"),
                        "shift_group": meta.get("shift_group"),
                        "is_shifted": meta.get("is_shifted"),
                        "abstained": meta.get("abstained"),
                        "mean_confidence": _mean_confidence(meta),
                        "components": meta.get("components", {}),
                        "probes": meta.get("probes", []),
                    }
                )

        if scores:
            per_replicate.append(sum(scores) / len(scores))
        if proxies:
            proxy_per_replicate.append(sum(proxies) / len(proxies))

    baselines, reference = run_baselines(env, split, limit=limit)
    aggregate = RunAggregate(
        env_id=env.env_id,
        model=model,
        per_replicate=per_replicate,
        baselines=baselines,
        proxy_per_replicate=proxy_per_replicate,
        reference_baseline=reference,
    )

    return RunResult(
        env_id=env.env_id,
        env_version=env.version,
        model=model,
        split=str(split),
        replicates=replicates,
        seed=seed,
        aggregate=aggregate,
        probe_metrics=_rollup_probes(per_scenario),
        shift_metrics=_rollup_shift(per_scenario),
        per_scenario=per_scenario,
        log_dir=resolved_log_dir,
    )


def _mean_confidence(meta: dict[str, Any]) -> float:
    """Recover mean stated confidence from the score components."""
    components = meta.get("components") or {}
    # `overconfidence` is mean confidence minus base rate, so adding the base rate back
    # recovers the mean. Stored this way to keep score metadata compact.
    if "overconfidence" in components and "n_items" in components:
        return float(components.get("overconfidence", 0.0))
    return 0.0


def write_card(result: RunResult, path: Path) -> Path:
    """Write the run card as committed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.as_card(), indent=2, sort_keys=True) + "\n")
    return path
