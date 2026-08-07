"""Snapshot access and claim verification for target_triage.

Everything here reads frozen files. No network call happens at eval time, which is what
makes a score from this environment comparable to a score produced last month or on
someone else's machine.

The claim vocabulary is the one design choice worth explaining. Supporting claims arrive
as structured tokens rather than prose, so verification is exact lookup rather than
interpretation. Free-text justifications would need a judge to check, and a judged
fabrication metric measures the judge as much as the model. The cost is that models must
cite in a fixed format; the benefit is that "this model fabricated 12% of its cited
evidence" means the same thing every time anyone runs it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from aimpoint.core.env import ClaimVerdict

#: Claim tokens the model may cite. Documented to the model in the scenario prompt.
CLAIM_VOCABULARY = {
    "target_exists": "target_exists:<TARGET_ID>",
    "no_prior_drug": "no_prior_drug:<TARGET_ID>:<DISEASE_ID>",
    "trialled_pre_cutoff": "trialled_pre_cutoff:<TARGET_ID>:<DISEASE_ID>",
    "approved_pre_cutoff": "approved_pre_cutoff:<TARGET_ID>:<DISEASE_ID>",
}


@dataclass(frozen=True)
class DiseaseEvidence:
    """Pre-cutoff therapeutic activity against one disease."""

    efo_id: str
    name: str
    approved_targets: frozenset[str]
    trialled_targets: frozenset[str]
    drugs: tuple[dict, ...]


class Snapshot:
    """The frozen pre-cutoff view of the therapeutic landscape."""

    def __init__(self, path: Path) -> None:
        self.path = path
        raw = json.loads((path / "snapshot.json").read_text())
        self.cutoff_year: int = raw["cutoff_year"]
        self.targets: dict[str, dict] = raw["targets"]
        self.mechanisms: list[dict] = raw["mechanisms"]
        self.drugs: list[dict] = raw["drugs"]
        self.diseases: list[dict] = raw["diseases"]

    @cached_property
    def target_of_molecule(self) -> dict[str, str]:
        return {m["molecule_chembl_id"]: m["target_chembl_id"] for m in self.mechanisms}

    @cached_property
    def mechanism_of_target(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for mech in self.mechanisms:
            out.setdefault(mech["target_chembl_id"], mech.get("mechanism_of_action") or "")
        return out

    @cached_property
    def evidence(self) -> dict[str, DiseaseEvidence]:
        """Per-disease pre-cutoff evidence, indexed by disease id."""
        approved: dict[str, set[str]] = {d["efo_id"]: set() for d in self.diseases}
        trialled: dict[str, set[str]] = {d["efo_id"]: set() for d in self.diseases}
        drugs: dict[str, list[dict]] = {d["efo_id"]: [] for d in self.diseases}

        for drug in self.drugs:
            efo = drug["disease"]
            if efo not in approved:
                continue
            drugs[efo].append(drug)
            target = self.target_of_molecule.get(drug["molecule_chembl_id"])
            if target is None:
                continue
            phase = drug.get("max_phase_for_indication") or 0.0
            if phase >= 4.0 and drug.get("first_approval"):
                approved[efo].add(target)
            if phase >= 2.0:
                trialled[efo].add(target)

        return {
            d["efo_id"]: DiseaseEvidence(
                efo_id=d["efo_id"],
                name=d["name"],
                approved_targets=frozenset(approved[d["efo_id"]]),
                trialled_targets=frozenset(trialled[d["efo_id"]]),
                drugs=tuple(drugs[d["efo_id"]]),
            )
            for d in self.diseases
        }

    def disease_by_name(self, name: str) -> DiseaseEvidence | None:
        lowered = name.strip().lower()
        for evidence in self.evidence.values():
            if evidence.name.lower() == lowered or evidence.efo_id.lower() == lowered:
                return evidence
        return None

    def search_targets(self, query: str, limit: int = 25) -> list[dict]:
        """Substring search over target names and accessions."""
        needle = query.strip().lower()
        if not needle:
            return []
        hits = [
            row
            for row in self.targets.values()
            if needle in (row.get("name") or "").lower()
            or any(needle == a.lower() for a in row.get("accessions", []))
        ]
        hits.sort(key=lambda r: (len(r.get("name") or ""), r.get("name") or ""))
        return hits[:limit]

    def verify_claim(self, claim: str) -> ClaimVerdict:
        """Check one structured claim token against the snapshot.

        Anything outside the documented vocabulary is `UNVERIFIABLE`, never
        `CONTRADICTED`. A model that cites something true in an unrecognised format has not
        fabricated anything, and scoring it as though it had would teach format compliance
        rather than accuracy.
        """
        parts = [p.strip() for p in claim.strip().split(":")]
        if len(parts) < 2 or parts[0] not in CLAIM_VOCABULARY:
            return ClaimVerdict.UNVERIFIABLE

        kind = parts[0]

        if kind == "target_exists":
            if len(parts) != 2:
                return ClaimVerdict.UNVERIFIABLE
            return ClaimVerdict.SUPPORTED if parts[1] in self.targets else ClaimVerdict.CONTRADICTED

        if len(parts) != 3:
            return ClaimVerdict.UNVERIFIABLE
        target, disease = parts[1], parts[2]

        evidence = self.evidence.get(disease) or self.disease_by_name(disease)
        if evidence is None:
            return ClaimVerdict.UNVERIFIABLE
        if target not in self.targets:
            # Asserting a relation about a target that does not exist is a fabrication,
            # unlike asserting an unrecognised relation about a real one.
            return ClaimVerdict.CONTRADICTED

        if kind == "approved_pre_cutoff":
            holds = target in evidence.approved_targets
        elif kind == "trialled_pre_cutoff":
            holds = target in evidence.trialled_targets
        else:  # no_prior_drug
            holds = (
                target not in evidence.trialled_targets and target not in evidence.approved_targets
            )

        return ClaimVerdict.SUPPORTED if holds else ClaimVerdict.CONTRADICTED


class AnswerKey:
    """Post-cutoff outcomes. Read by scorers, never reachable from a tool."""

    def __init__(self, path: Path) -> None:
        raw = json.loads(path.read_text())
        self.cutoff_year: int = raw["cutoff_year"]
        self._by_disease: dict[str, dict] = raw["by_disease"]

    def positives(self, efo_id: str) -> frozenset[str]:
        return frozenset(self._by_disease.get(efo_id, {}).get("positives", []))

    def negatives(self, efo_id: str) -> frozenset[str]:
        return frozenset(self._by_disease.get(efo_id, {}).get("negatives", []))

    def disease_name(self, efo_id: str) -> str:
        return self._by_disease.get(efo_id, {}).get("disease_name", efo_id)

    @property
    def disease_ids(self) -> list[str]:
        return sorted(self._by_disease)
