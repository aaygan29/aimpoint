"""The typed action protocol.

Every action a model takes reaches the harness as a validated Pydantic object produced
by a tool call. Nothing in Aimpoint parses prose to decide what a model did.

That rule exists for a measurement reason, not a stylistic one. When a scorer regexes
free text, part of what it measures is how closely a model's formatting habits match the
regex author's expectations. Two models with identical judgement then get different
scores, and the benchmark quietly becomes a formatting benchmark. Typed tool calls move
that variance to zero, which is what makes scores comparable across providers and stable
across reruns.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A probability, used for anything the model is asked to be calibrated about. Kept as a
# distinct alias so calibration scoring can find these fields generically.
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class ActionKind(StrEnum):
    """The universal action vocabulary.

    Environments define their own `QUERY` tools freely, but the other three are shared,
    because the cross-cutting probes depend on them existing everywhere. `REQUEST_INFO`
    is what makes abstention measurable: without a channel for "I need a fact you have
    not given me", a model that correctly recognises missing information has no way to
    express it and gets scored as though it had guessed.
    """

    QUERY = "query"
    REQUEST_INFO = "request_info"
    SUBMIT = "submit"
    ABSTAIN = "abstain"


class InfoRequest(BaseModel):
    """A request for a fact the scenario deliberately withheld."""

    model_config = ConfigDict(frozen=True)

    field: str = Field(description="Identifier of the withheld fact being requested.")
    reason: str = Field(default="", description="Why the decision cannot be made without it.")


class Submission(BaseModel):
    """Base class for a terminal answer.

    `abstained` is on the base rather than a subclass because declining to answer is a
    valid terminal move in every environment, and scoring it correctly (rewarding it when
    evidence is genuinely insufficient, penalising it when it is not) is one of the
    safety properties the harness exists to measure.
    """

    model_config = ConfigDict(frozen=True)

    abstained: bool = False
    abstention_reason: str = ""


class RankedItem(BaseModel):
    """One entry in a ranked shortlist.

    `supporting_claims` is what the fabrication probe consumes. Each string is a claim
    the model asserts as fact; the environment checks each against frozen data. A model
    that invents a plausible-sounding binding affinity to justify a ranking is caught
    mechanically, with no judge and no ambiguity about whether the claim was made.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(
        description="Identifier of the ranked entity, from the environment's namespace."
    )
    confidence: Confidence = Field(
        description="Probability the entry is correct by the environment's criterion."
    )
    rationale: str = Field(default="", description="Free text. Never scored by a primary scorer.")
    supporting_claims: list[str] = Field(
        default_factory=list,
        description="Factual assertions backing the entry, each checkable against frozen data.",
    )


class RankedSubmission(Submission):
    """A ranked, confidence-tagged, evidence-cited shortlist.

    This shape covers a large fraction of high-stakes decision support: triage,
    prioritisation, differential diagnosis, candidate screening. Supporting it natively
    means calibration and fabrication scoring are written once in the harness instead of
    once per environment.
    """

    items: list[RankedItem] = Field(default_factory=list)

    @field_validator("items")
    @classmethod
    def _no_duplicate_ids(cls, items: list[RankedItem]) -> list[RankedItem]:
        seen = set()
        for item in items:
            if item.id in seen:
                raise ValueError(f"duplicate id in ranked submission: {item.id!r}")
            seen.add(item.id)
        return items

    @property
    def ordered_ids(self) -> list[str]:
        """Ids in submitted rank order."""
        return [item.id for item in self.items]

    def confidence_for(self, item_id: str) -> float | None:
        for item in self.items:
            if item.id == item_id:
                return item.confidence
        return None


class ActionRecord(BaseModel):
    """One entry in the episode transcript.

    The transcript is the sole input to scoring alongside frozen data. Keeping it typed
    and complete is what makes a run reproducible from its log rather than only from a
    rerun.
    """

    model_config = ConfigDict(frozen=True)

    turn: int
    kind: ActionKind
    tool: str = ""
    arguments: dict = Field(default_factory=dict)
    result_digest: str = Field(
        default="", description="Hash of the tool result, so transcripts stay small but verifiable."
    )
