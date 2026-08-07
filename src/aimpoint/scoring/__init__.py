"""Scoring: calibration, ranking metrics, and replicate aggregation."""

from __future__ import annotations

from aimpoint.scoring import aggregate, calibration, ranking
from aimpoint.scoring.aggregate import Interval, RunAggregate, bootstrap_ci
from aimpoint.scoring.calibration import CalibrationReport, skill_score

__all__ = [
    "CalibrationReport",
    "Interval",
    "RunAggregate",
    "aggregate",
    "bootstrap_ci",
    "calibration",
    "ranking",
    "skill_score",
]
