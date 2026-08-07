"""Cross-cutting alignment probes.

These live in the harness rather than in individual environments so that every
contributed environment is instrumented the same way. An environment author declares what
a scenario withholds and what pressure it applies; the probes and their metrics are
supplied here. That is what keeps sycophancy scores comparable across environments written
by different people, and it means the cost of a new environment is domain logic only.
"""

from __future__ import annotations

from aimpoint.core.env import BeneficialEnv, Scenario
from aimpoint.core.episode import EpisodeResult
from aimpoint.probes import abstention, fabrication, shift, sycophancy
from aimpoint.probes.base import ProbeResult

__all__ = [
    "ProbeResult",
    "abstention",
    "fabrication",
    "run_all",
    "shift",
    "sycophancy",
]


def run_all(scenario: Scenario, episode: EpisodeResult, env: BeneficialEnv) -> list[ProbeResult]:
    """Run every per-episode probe. Inapplicable ones return an explicit marker."""
    return [
        sycophancy.run(scenario, episode),
        abstention.run(scenario, episode),
        fabrication.run(scenario, episode, env),
    ]
