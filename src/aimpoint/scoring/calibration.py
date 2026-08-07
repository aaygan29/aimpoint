"""Scoring stated confidences as probabilities.

Calibration is treated as a first-class capability here rather than a diagnostic, because
in any decision-support setting the number that determines whether a human should defer is
the model's confidence, not its accuracy. A model that is right 70% of the time and says so
is usable. One that is right 70% of the time and always says 95% is not, and no accuracy
metric distinguishes them.

The Brier score is decomposed the standard way (Murphy 1973) into reliability, resolution,
and uncertainty, because the two components fail differently and want different fixes.
Reliability is miscalibration: confidences that do not match observed frequencies. Resolution
is discrimination: whether the model separates cases at all. A model can post an unimpressive
Brier score through either, and only the decomposition says which.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Equal-width bins over [0, 1]. Ten is the convention in the calibration literature and
#: keeps bins populated at the sample sizes these environments realistically produce.
DEFAULT_BINS = 10


@dataclass(frozen=True)
class CalibrationReport:
    n: int
    brier: float
    reliability: float
    resolution: float
    uncertainty: float
    ece: float
    mean_confidence: float
    base_rate: float
    #: (bin_center, mean_confidence, observed_rate, count) for plotting a reliability curve.
    bins: tuple[tuple[float, float, float, int], ...]

    @property
    def overconfidence(self) -> float:
        """Mean confidence minus observed accuracy. Positive means overconfident."""
        return self.mean_confidence - self.base_rate

    def as_metrics(self) -> dict[str, float]:
        return {
            "brier": self.brier,
            "brier_reliability": self.reliability,
            "brier_resolution": self.resolution,
            "brier_uncertainty": self.uncertainty,
            "ece": self.ece,
            "mean_confidence": self.mean_confidence,
            "base_rate": self.base_rate,
            "overconfidence": self.overconfidence,
            "n_forecasts": float(self.n),
        }


def score(
    confidences: list[float], outcomes: list[bool], n_bins: int = DEFAULT_BINS
) -> CalibrationReport:
    """Score forecasts against binary outcomes.

    Args:
        confidences: Stated probabilities in [0, 1].
        outcomes: Whether each forecast turned out correct.
        n_bins: Bin count for the reliability decomposition and ECE.
    """
    if len(confidences) != len(outcomes):
        raise ValueError(
            f"confidences and outcomes differ in length: {len(confidences)} vs {len(outcomes)}"
        )
    if not confidences:
        return CalibrationReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ())

    f = np.clip(np.asarray(confidences, dtype=float), 0.0, 1.0)
    o = np.asarray(outcomes, dtype=float)
    n = len(f)

    brier = float(np.mean((f - o) ** 2))
    base_rate = float(np.mean(o))
    uncertainty = base_rate * (1.0 - base_rate)

    # Bin by forecast value. `np.digitize` with right=False puts 1.0 past the last edge,
    # so it is folded back into the top bin rather than silently dropped.
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(f, edges[1:-1], right=False), 0, n_bins - 1)

    reliability = 0.0
    resolution = 0.0
    ece = 0.0
    bins: list[tuple[float, float, float, int]] = []

    for k in range(n_bins):
        mask = idx == k
        count = int(mask.sum())
        center = float((edges[k] + edges[k + 1]) / 2.0)
        if count == 0:
            bins.append((center, float("nan"), float("nan"), 0))
            continue
        mean_f = float(f[mask].mean())
        obs = float(o[mask].mean())
        weight = count / n
        reliability += weight * (mean_f - obs) ** 2
        resolution += weight * (obs - base_rate) ** 2
        ece += weight * abs(mean_f - obs)
        bins.append((center, mean_f, obs, count))

    return CalibrationReport(
        n=n,
        brier=brier,
        reliability=float(reliability),
        resolution=float(resolution),
        uncertainty=float(uncertainty),
        ece=float(ece),
        mean_confidence=float(f.mean()),
        base_rate=base_rate,
        bins=tuple(bins),
    )


def skill_score(report: CalibrationReport) -> float:
    """Brier skill relative to always forecasting the base rate.

    1.0 is perfect, 0.0 means the forecasts carry no more information than knowing how
    often the event happens, and negative means they are worse than that. Reported because
    a raw Brier score is not interpretable without knowing the base rate: 0.09 is excellent
    on a balanced set and terrible on one where the answer is yes 95% of the time.
    """
    if report.uncertainty == 0.0:
        return 0.0
    return 1.0 - (report.brier / report.uncertainty)
