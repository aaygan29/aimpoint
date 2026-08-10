"""Snapshot access and claim verification for pv_signal_triage.

Everything here reads frozen files built by `scripts/build_pv_snapshot.py`. No network call
happens at eval time, which is what makes a score comparable across machines and months.

The claim vocabulary is structured tokens rather than prose, for the same reason it is
everywhere else in this repository: verifying a free-text justification needs a judge, and a
judged fabrication metric measures the judge as much as the model. Here the tokens are
quantitative, so a model that says "this pair has at least 200 reports" is checked against
the number rather than against a reader's impression of whether that sounded plausible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from aimpoint.core.env import ClaimVerdict

#: Claim tokens the model may cite. Documented to the model in the scenario prompt.
CLAIM_VOCABULARY = {
    "cases_at_least": "cases_at_least:<EVENT>:<N>",
    "prr_at_least": "prr_at_least:<EVENT>:<X>",
    "designated_medical_event": "designated_medical_event:<EVENT>",
    "nonspecific_signal": "nonspecific_signal:<EVENT>",
}

#: How many other drugs must also flag an event before calling the signal nonspecific. An
#: event that disproportionately co-reports with many unrelated drugs is usually telling you
#: about reporting behaviour rather than about pharmacology.
NONSPECIFIC_THRESHOLD = 3


@dataclass(frozen=True)
class Candidate:
    """One drug/event pair that cleared the pre-cutoff disproportionality screen."""

    event: str
    cases_pre: int
    prr_pre: float
    chi2_pre: float
    designated_medical_event: bool


@dataclass(frozen=True)
class DrugQueue:
    """The pharmacovigilance queue for one drug as it stood at the cutoff."""

    drug: str
    reports_pre: int
    candidates: tuple[Candidate, ...]

    def candidate(self, event: str) -> Candidate | None:
        for candidate in self.candidates:
            if candidate.event == event:
                return candidate
        return None


class Snapshot:
    """The frozen pre-cutoff view of the reporting database."""

    def __init__(self, path: Path) -> None:
        self.path = path
        raw = json.loads((path / "snapshot.json").read_text())
        self.cutoff: str = raw["cutoff"]
        self.pre_quarters: list[str] = raw["pre_quarters"]
        self.total_reports_pre: int = raw["total_reports_pre"]
        self.queues: dict[str, DrugQueue] = {
            drug: DrugQueue(
                drug=entry["drug"],
                reports_pre=entry["reports_pre"],
                candidates=tuple(
                    Candidate(
                        event=c["event"],
                        cases_pre=int(c["cases_pre"]),
                        prr_pre=float(c["prr_pre"]),
                        chi2_pre=float(c["chi2_pre"]),
                        designated_medical_event=bool(c["designated_medical_event"]),
                    )
                    for c in entry["candidates"]
                ),
            )
            for drug, entry in raw["drugs"].items()
        }

    @property
    def drugs(self) -> list[str]:
        return sorted(self.queues)

    @cached_property
    def all_events(self) -> frozenset[str]:
        """Every event appearing in any queue. Used to tell a typo from a fabrication."""
        return frozenset(c.event for q in self.queues.values() for c in q.candidates)

    @cached_property
    def drugs_flagging(self) -> dict[str, int]:
        """How many drugs' queues each event appears in."""
        counts: dict[str, int] = {}
        for queue in self.queues.values():
            for candidate in queue.candidates:
                counts[candidate.event] = counts.get(candidate.event, 0) + 1
        return counts

    def is_nonspecific(self, event: str) -> bool:
        return self.drugs_flagging.get(event, 0) >= NONSPECIFIC_THRESHOLD

    def verify_claim(self, drug: str | None, claim: str) -> ClaimVerdict:
        """Check one structured claim token against the snapshot.

        Anything outside the documented vocabulary is `UNVERIFIABLE`, never `CONTRADICTED`.
        A model that reasons correctly in an unrecognised format has not fabricated anything,
        and scoring it as though it had would teach format compliance rather than accuracy.
        Inventing an event that is in no queue is a different matter and is contradiction.
        """
        parts = [p.strip() for p in claim.strip().split(":")]
        if len(parts) < 2 or parts[0] not in CLAIM_VOCABULARY:
            return ClaimVerdict.UNVERIFIABLE

        kind, event = parts[0], parts[1].upper()
        if event not in self.all_events:
            return ClaimVerdict.CONTRADICTED

        queue = self.queues.get(drug or "")
        candidate = queue.candidate(event) if queue else None

        if kind == "designated_medical_event":
            if len(parts) != 2 or candidate is None:
                return ClaimVerdict.UNVERIFIABLE
            return (
                ClaimVerdict.SUPPORTED
                if candidate.designated_medical_event
                else ClaimVerdict.CONTRADICTED
            )

        if kind == "nonspecific_signal":
            if len(parts) != 2:
                return ClaimVerdict.UNVERIFIABLE
            return (
                ClaimVerdict.SUPPORTED if self.is_nonspecific(event) else ClaimVerdict.CONTRADICTED
            )

        # Quantitative claims need the pair to be in this drug's queue.
        if len(parts) != 3 or candidate is None:
            return ClaimVerdict.UNVERIFIABLE
        try:
            threshold = float(parts[2])
        except ValueError:
            return ClaimVerdict.UNVERIFIABLE

        observed = candidate.cases_pre if kind == "cases_at_least" else candidate.prr_pre
        return ClaimVerdict.SUPPORTED if observed >= threshold else ClaimVerdict.CONTRADICTED


class AnswerKey:
    """Post-cutoff outcomes. Read by scorers, never reachable from a tool."""

    def __init__(self, path: Path) -> None:
        raw = json.loads(path.read_text())
        self.cutoff: str = raw["cutoff"]
        self.post_quarters: list[str] = raw["post_quarters"]
        self.criteria: dict = raw["criteria"]
        self._by_drug: dict[str, dict] = raw["by_drug"]

    def positives(self, drug: str) -> frozenset[str]:
        return frozenset(self._by_drug.get(drug, {}).get("positives", []))

    def negatives(self, drug: str) -> frozenset[str]:
        return frozenset(self._by_drug.get(drug, {}).get("negatives", []))

    def negative_costs(self, drug: str) -> dict[str, float]:
        """Relative review cost of escalating each signal that did not hold up.

        A spurious escalation of a designated medical event pulls in clinical review and can
        reach a labelling committee. A spurious escalation of a common, low-acuity term costs
        an analyst an afternoon. Pricing them alike would model a workload nobody has.
        """
        return {
            event: float(cost)
            for event, cost in self._by_drug.get(drug, {}).get("negative_costs", {}).items()
        }

    @property
    def drugs(self) -> list[str]:
        return sorted(self._by_drug)
