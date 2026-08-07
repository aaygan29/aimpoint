"""target_triage: predicting which mechanisms earn a first approval, from a frozen past.

The v0 reference environment. Its job is to exercise every part of the harness end to end
and to give the beneficial-capability proposal something concrete to argue against. Its
scientific validity as a measure of drug-discovery judgement is *not* established, and the
README says so; treat scores from it as evidence the machinery works, not as evidence about
models' pharmacology.

Why this task shape rather than de novo design. The model reasons over molecular
interactions that are already characterised and already in the public record. It never
proposes new chemistry, so competence here does not transfer to synthesis planning. That
constraint is the environment's `asymmetry_rationale` and it is enforced by what the tools
expose: a catalogue of known targets and known drugs, and no way to describe a molecule
that does not already exist.
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai.tool import ToolDef

from aimpoint.core.determinism import SnapshotSpec
from aimpoint.core.env import (
    Baseline,
    BeneficialEnv,
    ClaimVerdict,
    PrimaryScore,
    RankedGroundTruth,
    Scenario,
    Split,
)
from aimpoint.core.protocol import RankedItem, RankedSubmission, Submission
from aimpoint.scoring import calibration, ranking

from . import scenarios as scenario_builder
from .data import AnswerKey, Snapshot

#: Weights over the three things the score cares about: finding the winners, avoiding the
#: known dead ends, and meaning what you say about your confidence. Discovery carries the
#: most because it is the task; calibration carries nearly as much because an uncalibrated
#: shortlist cannot be acted on by whoever receives it.
W_DISCOVERY = 0.45
W_AVOIDANCE = 0.25
W_CALIBRATION = 0.30

# Assets live beside the environment, so the whole thing is one self-contained folder a
# contributor can copy, review, or delete as a unit.
ASSETS = Path(__file__).resolve().parent / "assets"
SNAPSHOT_DIR = ASSETS / "snapshot"
ANSWERS_PATH = ASSETS / "answers.json"
MANIFEST_PATH = ASSETS / "manifest.json"


def _load_spec() -> SnapshotSpec | None:
    if not MANIFEST_PATH.exists():
        return None
    import json

    return SnapshotSpec.model_validate(json.loads(MANIFEST_PATH.read_text()))


class TargetTriageEnv(BeneficialEnv):
    env_id = "target_triage"
    version = "0.1.0"
    summary = (
        "Given the therapeutic landscape frozen at a cutoff year, predict which biological "
        "targets will earn their first approved drug for a given disease afterwards."
    )
    asymmetry_rationale = (
        "The model reasons over molecular interactions that are already characterised and "
        "already public: approved drugs, their annotated targets, and trial-stage "
        "programmes. It is never asked to design a molecule, propose a synthetic route, or "
        "describe a compound that does not already exist, and the tools expose no way to "
        "do so. Competence therefore consists of reading an existing evidence base well "
        "enough to tell promising mechanisms from dead ends, which is a skill whose "
        "offensive mirror image does not exist: knowing that a target failed in phase 3 "
        "confers no capability to cause harm. This matters because the obvious adjacent "
        "task, planning the synthesis of a bioactive molecule from first principles, is "
        "genuine uplift on synthesis planning, and a reward signal does not know that the "
        "molecule it was pointed at happened to be a medicine."
    )

    def __init__(self, snapshot_dir: Path | None = None, answers_path: Path | None = None) -> None:
        self.snapshot_path = snapshot_dir or SNAPSHOT_DIR
        self.snapshot_spec = _load_spec()
        self._snapshot = Snapshot(self.snapshot_path)
        self._answers = AnswerKey(answers_path or ANSWERS_PATH)

    # ---- scenarios ---------------------------------------------------------------

    def scenarios(self, split: Split) -> list[Scenario]:
        return scenario_builder.build(self._snapshot, self._answers, split)

    # ---- tools -------------------------------------------------------------------

    def tools(self, scenario: Scenario) -> list[ToolDef]:
        snap = self._snapshot

        async def list_diseases() -> str:
            """List the indications present in the frozen database."""
            lines = [f"{e.efo_id}\t{e.name}" for e in snap.evidence.values()]
            return "\n".join(sorted(lines))

        async def search_targets(query: str, limit: int = 25) -> str:
            """Search the human target catalogue by name or UniProt accession.

            Args:
                query: Substring of a target name, or an exact UniProt accession.
                limit: Maximum rows to return.
            """
            hits = snap.search_targets(query, limit=limit)
            if not hits:
                return f"No targets matched {query!r}."
            return "\n".join(
                f"{h['target_chembl_id']}\t{h.get('name')}\t{h.get('target_type')}" for h in hits
            )

        async def disease_landscape(disease_id: str) -> str:
            """Pre-cutoff therapeutic activity against one indication.

            Args:
                disease_id: Disease identifier, for example MONDO:0005148.
            """
            evidence = snap.evidence.get(disease_id) or snap.disease_by_name(disease_id)
            if evidence is None:
                return (
                    f"No indication {disease_id!r} in the frozen database. "
                    "Call list_diseases for the available identifiers."
                )

            by_target: dict[str, list[dict]] = {}
            for drug in evidence.drugs:
                target = snap.target_of_molecule.get(drug["molecule_chembl_id"])
                if target:
                    by_target.setdefault(target, []).append(drug)

            lines = [f"{evidence.name} ({evidence.efo_id}), frozen at {snap.cutoff_year}", ""]
            for target in sorted(
                by_target,
                key=lambda t: -max(d.get("max_phase_for_indication") or 0 for d in by_target[t]),
            ):
                drugs = by_target[target]
                phase = max(d.get("max_phase_for_indication") or 0 for d in drugs)
                status = "approved" if target in evidence.approved_targets else "trials only"
                name = (snap.targets.get(target) or {}).get("name") or "?"
                lines.append(
                    f"{target}\t{name}\tmax_phase={phase:.0f}\t{status}\tn_programmes={len(drugs)}"
                )
            return "\n".join(lines)

        async def target_profile(target_id: str) -> str:
            """Everything the frozen database holds about one target.

            Args:
                target_id: Target ChEMBL id, for example CHEMBL1784.
            """
            row = snap.targets.get(target_id)
            if row is None:
                return f"No target {target_id!r} in the catalogue."
            lines = [
                f"{target_id}\t{row.get('name')}",
                f"type: {row.get('target_type')}",
                f"accessions: {', '.join(row.get('accessions', [])) or 'none'}",
                f"annotated mechanism: {snap.mechanism_of_target.get(target_id) or 'none recorded'}",
                "",
                "status by indication (pre-cutoff):",
            ]
            for evidence in snap.evidence.values():
                if target_id in evidence.approved_targets:
                    status = "approved"
                elif target_id in evidence.trialled_targets:
                    status = "in trials"
                else:
                    status = "no recorded programme"
                lines.append(f"  {evidence.efo_id}\t{evidence.name}\t{status}")
            return "\n".join(lines)

        return [
            ToolDef(list_diseases),
            ToolDef(search_targets),
            ToolDef(disease_landscape),
            ToolDef(target_profile),
        ]

    # ---- scoring -----------------------------------------------------------------

    def score_primary(self, scenario: Scenario, submission: Submission) -> PrimaryScore:
        truth = scenario.ground_truth
        if not isinstance(truth, RankedGroundTruth) or not isinstance(submission, RankedSubmission):
            return PrimaryScore(headline=0.0, notes="unsupported scenario or submission type")

        # Scenarios where declining is the right answer are scored on that alone. Mixing
        # them into the ranking metrics would let a model earn partial credit for producing
        # a shortlist it should not have produced.
        if truth.abstention_is_correct:
            correct = bool(submission.abstained)
            return PrimaryScore(
                headline=1.0 if correct else 0.0,
                components={"correct_abstention": float(correct)},
                notes="abstention scenario: the evidence does not support a shortlist",
            )

        if submission.abstained:
            return PrimaryScore(
                headline=0.0,
                components={"over_abstention": 1.0},
                notes="declined an answerable scenario",
            )

        if not submission.items:
            return PrimaryScore(headline=0.0, components={"empty": 1.0}, notes="empty shortlist")

        discovery = ranking.average_precision(submission.ordered_ids, truth.positives)
        burden = ranking.negative_burden(submission, truth.negatives)
        avoidance = 1.0 - burden

        confidences, outcomes = ranking.outcomes_for_calibration(submission, truth.positives)
        report = calibration.score(confidences, outcomes)
        # Skill is relative to forecasting the base rate, and can go negative when
        # confidences are worse than knowing nothing. Clipped at zero so a single badly
        # calibrated component cannot drag the headline below the floor a no-op earns.
        cal = max(0.0, calibration.skill_score(report))

        headline = W_DISCOVERY * discovery + W_AVOIDANCE * avoidance + W_CALIBRATION * cal
        return PrimaryScore(
            headline=headline,
            components={
                "discovery_ap": discovery,
                "avoidance": avoidance,
                "calibration_skill": cal,
                "brier": report.brier,
                "overconfidence": report.overconfidence,
                "n_items": float(len(submission.items)),
            },
        )

    def proxy_score(self, scenario: Scenario, submission: Submission) -> float | None:
        """Recall at any rank, with no penalty for list length or overconfidence.

        The metric a hurried designer ships. A model can drive it to 1.0 by listing the
        whole catalogue, which is exactly why the harness reports the gap between it and
        the real score.
        """
        truth = scenario.ground_truth
        if not isinstance(truth, RankedGroundTruth) or not isinstance(submission, RankedSubmission):
            return None
        if truth.abstention_is_correct:
            return None
        return ranking.recall_at_any(submission, truth.positives)

    def verify_claim(self, scenario: Scenario, claim: str) -> ClaimVerdict:
        return self._snapshot.verify_claim(claim)

    # ---- baselines ---------------------------------------------------------------

    def baselines(self) -> list[Baseline]:
        return [
            Baseline("noop", "Submits an empty shortlist. The floor.", _noop, role="floor"),
            Baseline(
                "always_abstain",
                "Declines every scenario. Reveals whether abstention scoring is degenerate.",
                _always_abstain,
                role="floor",
            ),
            Baseline(
                "prior_art",
                "Ranks targets already in trials for the indication by how far they got. "
                "What a careful analyst with the same data and no biology would do.",
                self._prior_art,
                role="reference",
            ),
            Baseline(
                "spec_gamer",
                "Names hundreds of targets at hedged confidence. Written to beat the proxy "
                "metric while being useless, so the proxy gap is demonstrable rather than "
                "hypothetical.",
                self._spec_gamer,
                role="adversarial",
            ),
        ]

    def _spec_gamer(self, scenario: Scenario) -> RankedSubmission:
        """Submit a very long hedged list. An honest demonstration of the failure mode.

        Against `recall_at_any` this policy is close to unbeatable, because naming enough
        candidates guarantees the right ones appear somewhere. Against the real score it
        collapses, since average precision punishes burying the answer and the calibration
        term punishes asserting a probability on hundreds of entries that will not pan out.

        It exists so that the difference between the two metrics is something a reader can
        run rather than something they have to take on faith. If a future change to the
        scoring lets this policy score well, that change broke the environment.
        """
        disease = scenario.metadata.get("disease")
        if disease is None:
            return RankedSubmission()
        evidence = self._snapshot.evidence.get(disease)
        if evidence is None:
            return RankedSubmission()

        # Everything ever touched for this indication, plus a slice of the wider catalogue.
        pool = sorted(evidence.trialled_targets | evidence.approved_targets)
        pool += [t for t in sorted(self._snapshot.targets) if t not in set(pool)][:400]
        return RankedSubmission(
            items=[
                RankedItem(id=target, confidence=0.3, supporting_claims=[f"target_exists:{target}"])
                for target in pool[:400]
            ]
        )

    def _prior_art(self, scenario: Scenario) -> RankedSubmission:
        """Rank pre-cutoff trial-stage targets by furthest phase reached.

        A real reference rather than a strawman: "the things furthest along are most likely
        to arrive" is the default heuristic in portfolio review, and it is a genuinely hard
        line for a model to beat. Its confidences reflect actual late-stage attrition rather
        than optimism, so it is not trivially beaten on calibration either.
        """
        disease = scenario.metadata.get("disease")
        if disease is None:
            return RankedSubmission(abstained=True, abstention_reason="no indication given")

        evidence = self._snapshot.evidence.get(disease)
        if evidence is None:
            return RankedSubmission()

        candidates = evidence.trialled_targets - evidence.approved_targets
        phases: dict[str, float] = {}
        for drug in evidence.drugs:
            target = self._snapshot.target_of_molecule.get(drug["molecule_chembl_id"])
            if target in candidates:
                phases[target] = max(
                    phases.get(target, 0.0), drug.get("max_phase_for_indication") or 0.0
                )

        ordered = sorted(phases.items(), key=lambda kv: (-kv[1], kv[0]))
        items = [
            RankedItem(
                id=target,
                # Late-stage programmes still mostly do not arrive. These numbers are
                # deliberately modest so the baseline is calibrated rather than confident.
                confidence=0.15 if phase >= 3.0 else 0.07,
                supporting_claims=[f"trialled_pre_cutoff:{target}:{disease}"],
            )
            for target, phase in ordered[:20]
        ]
        return RankedSubmission(items=items)


def _noop(scenario: Scenario) -> RankedSubmission:
    return RankedSubmission()


def _always_abstain(scenario: Scenario) -> RankedSubmission:
    return RankedSubmission(abstained=True, abstention_reason="baseline: always declines")
