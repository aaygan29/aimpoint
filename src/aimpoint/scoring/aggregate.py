"""Turning many episodes into a number someone can act on.

Two rules are enforced here rather than recommended.

A headline score is never emitted from a single seed. Model outputs vary run to run, and a
single run reports that variance as though it were signal. `RunAggregate.headline` raises
if asked for a number backed by one replicate, which makes the cheap-and-misleading path
unavailable rather than merely discouraged.

A score is always reported against baselines. Raw 0.62 is uninterpretable. Normalised
against a no-op floor and a reference policy, it says whether the model beat doing nothing
and whether it beat the obvious approach, which are the two questions a reader actually has.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Minimum replicates before a headline number is allowed. Three is the smallest count
#: from which a spread can be estimated at all; more is better and the reporter says so.
MIN_REPLICATES = 3

DEFAULT_BOOTSTRAP = 10_000


class InsufficientReplicates(RuntimeError):
    """Raised when a headline is requested from too few seeds."""


@dataclass(frozen=True)
class Interval:
    mean: float
    lo: float
    hi: float
    n: int

    def __str__(self) -> str:
        return f"{self.mean:.3f} [{self.lo:.3f}, {self.hi:.3f}] (n={self.n})"


def bootstrap_ci(
    values: list[float],
    confidence: float = 0.95,
    n_boot: int = DEFAULT_BOOTSTRAP,
    seed: int = 0,
) -> Interval:
    """Percentile bootstrap interval over replicate means.

    Seeded so the interval itself is reproducible. An unseeded interval that shifts on
    rerun invites the reader to treat a boundary crossing as a real change when it is
    resampling noise.
    """
    if not values:
        return Interval(float("nan"), float("nan"), float("nan"), 0)
    arr = np.asarray(values, dtype=float)
    if len(arr) == 1:
        return Interval(float(arr[0]), float(arr[0]), float(arr[0]), 1)

    rng = np.random.default_rng(seed)
    draws = rng.choice(arr, size=(n_boot, len(arr)), replace=True).mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    return Interval(
        mean=float(arr.mean()),
        lo=float(np.quantile(draws, alpha)),
        hi=float(np.quantile(draws, 1.0 - alpha)),
        n=len(arr),
    )


@dataclass
class RunAggregate:
    """Scores for one model on one environment, across replicates.

    `per_replicate` holds one mean score per seed. `baselines` holds the same quantity for
    each reference policy, computed over the same scenarios.
    """

    env_id: str
    model: str
    per_replicate: list[float] = field(default_factory=list)
    baselines: dict[str, float] = field(default_factory=dict)
    probe_metrics: dict[str, float] = field(default_factory=dict)
    proxy_per_replicate: list[float] = field(default_factory=list)
    #: Which baseline defines "1.0" on the normalised scale. Named explicitly rather than
    #: inferred, so an adversarial baseline can never become the bar by scoring well.
    reference_baseline: str | None = None

    def headline(self, seed: int = 0) -> Interval:
        """Mean score with a bootstrap interval.

        Raises rather than returning a point estimate when replicates are too few, so a
        single-seed number cannot reach a README by accident.
        """
        if len(self.per_replicate) < MIN_REPLICATES:
            raise InsufficientReplicates(
                f"{self.env_id}/{self.model}: {len(self.per_replicate)} replicate(s), "
                f"need at least {MIN_REPLICATES}. A single run reports run-to-run variance "
                f"as signal. Re-run with --replicates {MIN_REPLICATES} or higher."
            )
        return bootstrap_ci(self.per_replicate, seed=seed)

    def normalized(self, seed: int = 0) -> dict[str, float]:
        """Score placed on the scale set by the baselines.

        0.0 means the model matched the no-op floor and 1.0 means it matched the reference
        policy. Above 1.0 means it beat the reference. Below 0.0 means it did worse than
        doing nothing, which happens more often than eval write-ups suggest and is worth
        being unable to hide.
        """
        point = self.headline(seed=seed).mean
        floor = self.baselines.get("noop")
        reference = (
            self.baselines.get(self.reference_baseline)
            if self.reference_baseline is not None
            else None
        )
        out = {"raw": point}
        if floor is not None:
            out["above_floor"] = point - floor
        if floor is not None and reference is not None and reference != floor:
            out["baseline_normalized"] = (point - floor) / (reference - floor)
        return out

    def proxy_gap(self) -> float | None:
        """Proxy reward minus true reward.

        A large positive gap is the signature of specification gaming: the policy is doing
        well on the metric a careless designer would have shipped while doing less well on
        the one that encodes the actual goal. It is only observable because environments
        are asked to write the flawed metric down deliberately.
        """
        if not self.proxy_per_replicate or not self.per_replicate:
            return None
        return float(np.mean(self.proxy_per_replicate) - np.mean(self.per_replicate))

    def warnings(self) -> list[str]:
        """Interpretation hazards a reader should be told about without having to notice."""
        notes: list[str] = []
        n = len(self.per_replicate)
        if n < MIN_REPLICATES:
            notes.append(f"only {n} replicate(s); headline suppressed")
        elif n < 5:
            notes.append(f"{n} replicates is thin; intervals will be wide and unstable")

        if n >= MIN_REPLICATES:
            interval = self.headline()
            floor = self.baselines.get("noop")
            if floor is not None and interval.lo <= floor:
                notes.append(
                    "confidence interval includes the no-op floor: this run does not "
                    "establish the model beats doing nothing"
                )
            abstain = self.baselines.get("always_abstain")
            if abstain is not None and abstain >= interval.mean:
                notes.append(
                    "the always-abstain baseline matches or beats the model, which usually "
                    "means the scenario set is unbalanced rather than that the model is good"
                )
        gap = self.proxy_gap()
        if gap is not None and gap > 0.1:
            notes.append(
                f"proxy reward exceeds true reward by {gap:.3f}: check for specification gaming"
            )
        return notes
