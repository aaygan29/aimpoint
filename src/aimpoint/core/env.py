"""The environment plugin interface.

An environment supplies scenarios, tools, ground truth, and a judge-free primary scorer.
The harness supplies episodes, probes, calibration, aggregation, baselines, and the
reproducibility gates. That split is the point: contributing an environment should mean
writing domain logic, not re-deriving how to measure sycophancy or how to bootstrap a
confidence interval.

Note what `score_primary` is not given: a model. The headline metric cannot become a
judged metric by accident, because there is nothing in scope to judge with.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aimpoint.core.determinism import SnapshotSpec
from aimpoint.core.protocol import Submission


class Split(StrEnum):
    """Public development split, and a held-out split whose labels are not published.

    The held-out split exists because this artifact is designed to be trained against.
    An environment that ships all its answers is a benchmark with an expiry date.
    """

    DEV = "dev"
    TEST = "test"


class ProbeKind(StrEnum):
    SYCOPHANCY = "sycophancy"
    ABSTENTION = "abstention"
    FABRICATION = "fabrication"
    SHIFT = "shift"


class ClaimVerdict(StrEnum):
    """Result of checking a model-asserted claim against frozen data.

    `UNVERIFIABLE` is kept distinct from `CONTRADICTED` on purpose. Conflating them would
    punish a model for citing something true that the snapshot simply does not cover,
    which teaches reticence rather than accuracy. Only `CONTRADICTED` counts as
    fabrication.
    """

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class SycophancyPressure:
    """A scripted push toward a known-wrong answer, injected mid-episode.

    Scripted rather than model-generated so the pressure is identical for every model and
    every rerun. A model-generated interlocutor would make the stimulus itself a variable,
    and then a lower sycophancy score might only mean the pressure happened to be weaker.
    """

    turn: int
    message: str
    endorsed_id: str
    endorsed_is_wrong: bool = True


@dataclass(frozen=True)
class GroundTruth:
    """Marker base. Environments subclass with whatever their scorer needs."""


@dataclass(frozen=True)
class RankedGroundTruth(GroundTruth):
    """Answer key for a ranked shortlist task.

    `negatives` is tracked separately from "everything not positive" because knowing that
    a candidate was actively tried and failed is different evidence from never having been
    tried, and a scorer that treats them alike gives no credit for avoiding known dead ends.

    `negative_costs` prices the false positives against each other. Leaving it empty means
    every wrong entry costs the same, which is the right default when a domain has no
    principled way to rank its mistakes. Many domains do. Escalating a spurious
    agranulocytosis signal consumes review capacity that escalating a spurious nausea signal
    does not, and a false accusation of one kind can be far more damaging to a user than a
    false accusation of another. Where that ordering is known and defensible, writing it down
    is more honest than letting a uniform metric imply the mistakes are interchangeable.

    Costs are relative, not absolute: only their ratios affect the score, because the burden
    they feed is normalised against the worst case the model could have produced. An
    environment should therefore ship the ratios it can argue for and leave the rest at 1.0,
    rather than inventing a unit.
    """

    positives: frozenset[str] = frozenset()
    negatives: frozenset[str] = frozenset()
    abstention_is_correct: bool = False
    #: Relative cost of listing each negative. Missing entries cost 1.0.
    negative_costs: Mapping[str, float] = field(default_factory=dict)

    def cost_of(self, item_id: str) -> float:
        """Relative cost of listing one known-wrong entry."""
        return float(self.negative_costs.get(item_id, 1.0))


@dataclass(frozen=True)
class Scenario:
    """One task instance.

    `withheld` holds facts the operator has but the prompt omits. They are revealed only
    if the model asks via `request_info`. `decisive_fields` marks the subset whose absence
    should block a responsible answer, which is what the abstention probe scores against:
    not whether the model asked questions, but whether it asked the ones that mattered
    before committing.
    """

    id: str
    split: Split
    prompt: str
    ground_truth: GroundTruth
    withheld: dict[str, str] = field(default_factory=dict)
    decisive_fields: frozenset[str] = frozenset()
    pressure: SycophancyPressure | None = None
    shift_group: str | None = None
    is_shifted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def probes(self) -> frozenset[ProbeKind]:
        """Which probes this scenario can support, inferred from what it declares."""
        kinds = {ProbeKind.FABRICATION}
        if self.pressure is not None:
            kinds.add(ProbeKind.SYCOPHANCY)
        if self.decisive_fields:
            kinds.add(ProbeKind.ABSTENTION)
        if self.shift_group is not None:
            kinds.add(ProbeKind.SHIFT)
        return frozenset(kinds)


class PrimaryScore(BaseModel):
    """A judge-free score.

    `headline` is the single comparable number. `components` carries the breakdown, which
    matters because a headline that moves without any component moving is a bug, and a
    headline nobody can decompose is a number nobody should trust.
    """

    model_config = ConfigDict(frozen=True)

    headline: float
    components: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


@dataclass(frozen=True)
class Baseline:
    """A reference policy that needs no model.

    Every environment must ship these. Without a floor and a credible reference, a score
    of 0.62 is not interpretable: it could be excellent or worse than answering at random,
    and the reader has no way to tell.

    `role` keeps the three kinds apart. `floor` is the do-nothing bound, `reference` is the
    line a model has to beat to be worth anything, and `adversarial` is a policy written
    deliberately to game the proxy metric. Adversarial baselines must never be treated as
    the reference, since a gamer that scores well would silently raise the bar it was
    written to expose.
    """

    name: str
    describe: str
    policy: Any  # Callable[[Scenario], Submission]
    role: str = "reference"


class BeneficialEnv(ABC):
    """Base class for a beneficial-capability environment."""

    env_id: str
    version: str
    summary: str
    #: Why competence here has no symmetric offensive use. Required prose, checked for
    #: presence by `aimpoint validate`, because "beneficial" is the claim most likely to
    #: be assumed rather than argued.
    asymmetry_rationale: str
    snapshot_spec: SnapshotSpec | None = None
    snapshot_path: Path | None = None

    @abstractmethod
    def scenarios(self, split: Split) -> list[Scenario]:
        """All scenarios in a split."""

    @abstractmethod
    def tools(self, scenario: Scenario) -> list[Any]:
        """Inspect tools the model may call. Information gathering only.

        Terminal actions (`submit`, `abstain`) and `request_info` are supplied by the
        harness so their semantics are identical everywhere.
        """

    @abstractmethod
    def score_primary(self, scenario: Scenario, submission: Submission) -> PrimaryScore:
        """Judge-free headline score. Receives no model, by design."""

    @abstractmethod
    def verify_claim(self, scenario: Scenario, claim: str) -> ClaimVerdict:
        """Check one model-asserted claim against frozen data."""

    @abstractmethod
    def baselines(self) -> list[Baseline]:
        """Reference policies. Must include a no-op floor."""

    def score_secondary(self, scenario: Scenario, submission: Submission) -> dict[str, float]:
        """Optional extras. May use a judge. Never enters the headline."""
        return {}

    def proxy_score(self, scenario: Scenario, submission: Submission) -> float | None:
        """An intentionally flawed reward, for measuring specification gaming.

        Return the metric a well-meaning but careless designer would have reached for.
        The harness reports the gap between it and the true score. A large gap on a model
        that scores well on the proxy is the signature of a policy optimising the measure
        rather than the goal, and it is only visible if someone writes the flawed metric
        down on purpose.
        """
        return None
