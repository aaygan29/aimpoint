"""Shared probe types.

A probe reads an episode and reports metrics about *how* an answer was reached rather
than whether it was right. That distinction is the reason probes live in the harness: a
model can reach a correct shortlist by fabricating its evidence, by capitulating to
whoever spoke last, or by guessing past a fact it should have asked for, and a scorer
that only compares the answer to the key cannot tell any of those apart.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from aimpoint.core.env import ProbeKind


class ProbeResult(BaseModel):
    """Metrics from one probe on one episode.

    `applicable` is separate from empty metrics because "this scenario carried no pressure"
    and "this model did not capitulate" must never be averaged together. Silently treating
    an inapplicable probe as a zero would dilute the measured rate toward whatever fraction
    of scenarios happened to carry the probe.
    """

    model_config = ConfigDict(frozen=True)

    kind: ProbeKind
    applicable: bool
    metrics: dict[str, float] = Field(default_factory=dict)
    detail: str = ""

    @classmethod
    def not_applicable(cls, kind: ProbeKind, why: str = "") -> ProbeResult:
        return cls(kind=kind, applicable=False, detail=why)
