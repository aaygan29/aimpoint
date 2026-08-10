"""pv_signal_triage: which disproportionality signals hold up, and which were noise.

The capability. A pharmacovigilance queue is a list of drug/event pairs that cleared a
statistical screen. Clearing the screen is not evidence of a drug effect: most
disproportionate pairs in spontaneous reporting reflect confounding by indication, publicity
driving reporting, or the background frequency of a common term. Someone has to decide which
ones are worth a case series, and that decision is made under sparse evidence with no
feedback for years.

Why this is a safety capability rather than a general one. The failure that degrades real
pharmacovigilance is not missing signals, it is drowning in them. Alert systems that escalate
everything get overridden, and once they are overridden the real signal is missed too. That
is the same pathology `safety_judgment` measures in a different domain, and it is invisible to
the metric the field reaches for first, which is recall on the signals that turned out real.

So the two errors are scored together, combined with a harmonic mean so neither can be traded
for the other, and the false positives are priced against each other. Escalating a spurious
agranulocytosis pulls in clinical review and can reach a labelling committee; escalating a
spurious nausea costs an analyst an afternoon. The answer key carries that ratio, and the
scorer uses it. A metric that prices them alike is not modelling the workload it claims to.

`proxy_score` is the naive metric, shipped deliberately: recall on the signals that held up,
ignoring how many that did not were escalated alongside them. The `escalate_everything`
baseline drives it to 1.0.
"""

from __future__ import annotations

import json
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
from .data import NONSPECIFIC_THRESHOLD, AnswerKey, Snapshot

#: Identifying which signals hold up is the task, so the core term dominates. Calibration
#: carries the rest because the number that decides whether a safety physician acts on a
#: triaged queue is the stated probability, not the ordering.
W_CORE = 0.65
W_CALIBRATION = 0.35

#: The reference baseline applies the conventional screen threshold to a queue that was
#: built at a lower one. That is exactly what a signal-detection group does with a marginal
#: queue, which makes it a real reference rather than a strawman, and it leaves out the
#: sub-threshold pairs so it does not trivially saturate the recall proxy.
REFERENCE_PRR = 2.0
REFERENCE_MAX_ITEMS = 40

#: Share of the review cost incurred by escalating a pair at all, before confidence is
#: considered. Escalation here is an act, not advice: a pair submitted at 0.1 confidence still
#: lands on a safety physician's desk and still consumes the capacity a real signal needed.
#: Leaving this at the harness default of 0 let `escalate_everything` send the whole queue up
#: at hedged confidence and pay a fraction of the price, which is the alert-fatigue policy
#: bought at a discount, and it outscored triage until this was fixed.
LISTING_FLOOR = 0.75

ASSETS = Path(__file__).resolve().parent / "assets"
SNAPSHOT_DIR = ASSETS / "snapshot"
ANSWERS_PATH = ASSETS / "answers.json"
MANIFEST_PATH = ASSETS / "manifest.json"


def _load_spec() -> SnapshotSpec | None:
    if not MANIFEST_PATH.exists():
        return None
    return SnapshotSpec.model_validate(json.loads(MANIFEST_PATH.read_text()))


def _calibration_credit(report: calibration.CalibrationReport) -> float:
    """Calibration credit that stays defined when a submission has no outcome variance.

    Brier skill is measured against forecasting the base rate and is undefined when the base
    rate is 0 or 1, where `skill_score` returns 0.0. A short, entirely correct escalation list
    hits that case, and taking the default would cap a perfect triage below the top of the
    scale and make the calibration term reachable only by adding a wrong entry.

    The branches are asymmetric on purpose. If everything escalated held up, what remains to
    score is whether the stated confidence matched the outcome, which is `1 - brier`. If
    nothing escalated held up, confidence earns no credit at any value: rewarding a uniformly
    wrong list for hedging is the behaviour the rest of this scorer exists to catch.
    """
    if report.n == 0:
        return 0.0
    if report.uncertainty > 0.0:
        return max(0.0, calibration.skill_score(report))
    if report.base_rate >= 1.0:
        return max(0.0, 1.0 - report.brier)
    return 0.0


def _harmonic(a: float, b: float) -> float:
    """Harmonic mean, so sensitivity cannot be bought with specificity or the reverse.

    A weighted sum would let a model escalate the whole queue and recover most of its score
    on discovery, which is exactly the alert-fatigue policy this environment exists to
    penalise.
    """
    if a <= 0.0 or b <= 0.0:
        return 0.0
    return 2.0 * a * b / (a + b)


class PvSignalTriageEnv(BeneficialEnv):
    env_id = "pv_signal_triage"
    version = "0.1.0"
    summary = (
        "Given a pharmacovigilance queue of drug/event pairs that cleared the "
        "disproportionality screen before a cutoff, rank which still signal years later. "
        "Scored symmetrically on missed signals and on review burden, with false escalations "
        "priced by the seriousness of the event."
    )
    asymmetry_rationale = (
        "The model reads spontaneous adverse event reports that are already public and "
        "already aggregated, and decides which statistical associations deserve human "
        "review. Competence consists of telling a pharmacological signal from confounding by "
        "indication, notoriety bias, and background frequency. There is no offensive mirror "
        "image of that skill: knowing that a reported association did not hold up confers no "
        "capability to cause harm, and knowing that one did is the content of a drug label. "
        "The model is never asked to design a molecule, propose a synthetic route, suggest a "
        "dose, or give clinical advice, and the tools expose no way to do any of it. This is "
        "stated explicitly because the adjacent task that would fail the test, asking a model "
        "which drug and dose produces a given physiological effect, is genuine uplift toward "
        "harm, and a reward signal does not know that the effect it was pointed at happened "
        "to be an adverse one someone wanted to prevent."
    )

    def __init__(self, snapshot_dir: Path | None = None, answers_path: Path | None = None) -> None:
        self.snapshot_path = snapshot_dir or SNAPSHOT_DIR
        self.snapshot_spec = _load_spec()
        self._snapshot = Snapshot(self.snapshot_path)
        self._answers = AnswerKey(answers_path or ANSWERS_PATH)

    # ---- scenarios ---------------------------------------------------------------

    def scenarios(self, split: Split) -> list[Scenario]:
        return scenario_builder.build(self._snapshot, self._answers, split)

    def _queue_for(self, scenario: Scenario):
        return self._snapshot.queues.get(scenario.metadata.get("drug", ""))

    # ---- tools -------------------------------------------------------------------

    def tools(self, scenario: Scenario) -> list[ToolDef]:
        """Lookups over the frozen pre-cutoff database.

        Deliberately absent: any way to list another drug's queue. Those queues are
        pre-cutoff and would leak nothing about the future, but they would let a model
        identify the withheld medicine in the shift and abstention variants by matching event
        profiles, which would quietly convert those probes into a retrieval exercise.
        """
        snapshot = self._snapshot
        queue = self._queue_for(scenario)

        async def screen_criteria() -> str:
            """The screen that built this queue, and what clearing it does and does not mean."""
            return (
                f"Database frozen at {snapshot.cutoff}, covering "
                f"{snapshot.pre_quarters[0]} to {snapshot.pre_quarters[-1]}.\n"
                f"Total reports in window: {snapshot.total_reports_pre}\n\n"
                "A pair entered this queue by clearing: at least 15 co-reported cases with "
                "the drug as primary or secondary suspect, a proportional reporting ratio of "
                "at least 2, and a Yates-corrected chi-square of at least 4.\n\n"
                "Clearing the screen means the pair is reported more often with this drug "
                "than the database background. It is not evidence of causation. Confounding "
                "by indication, publicity, and common background terms all produce it."
            )

        async def event_detail(event: str) -> str:
            """Everything the frozen database holds about one pair in this queue.

            Args:
                event: Event term, for example DIABETIC KETOACIDOSIS.
            """
            if queue is None:
                return "No queue is attached to this case."
            candidate = queue.candidate(event.strip().upper())
            if candidate is None:
                return f"{event!r} is not in this queue. The queue is listed in your briefing."
            return (
                f"{candidate.event}\n"
                f"co-reported cases: {candidate.cases_pre}\n"
                f"proportional reporting ratio: {candidate.prr_pre:.2f}\n"
                f"chi-square: {candidate.chi2_pre:.1f}\n"
                f"designated medical event: {candidate.designated_medical_event}\n"
                f"drugs in this database whose queue also contains this event: "
                f"{snapshot.drugs_flagging.get(candidate.event, 0)}"
            )

        async def event_specificity(event: str) -> str:
            """How many unrelated medicines flag the same event before the cutoff.

            Args:
                event: Event term to check.
            """
            term = event.strip().upper()
            if term not in snapshot.all_events:
                return f"{term!r} does not appear in any queue in this database."
            count = snapshot.drugs_flagging.get(term, 0)
            verdict = "nonspecific" if count >= NONSPECIFIC_THRESHOLD else "relatively specific"
            return (
                f"{term}: appears in {count} of {len(snapshot.queues)} drug queues "
                f"({verdict} at a threshold of {NONSPECIFIC_THRESHOLD}).\n"
                "An event that co-reports disproportionately with many unrelated medicines is "
                "usually describing reporting behaviour rather than pharmacology."
            )

        async def most_nonspecific(limit: int = 20) -> str:
            """Events flagged across the most drug queues in the frozen database.

            Args:
                limit: Maximum rows to return.
            """
            rows = sorted(snapshot.drugs_flagging.items(), key=lambda kv: (-kv[1], kv[0]))
            return "\n".join(f"{event}\t{count} queues" for event, count in rows[:limit])

        return [
            ToolDef(screen_criteria),
            ToolDef(event_detail),
            ToolDef(event_specificity),
            ToolDef(most_nonspecific),
        ]

    # ---- scoring -----------------------------------------------------------------

    def score_primary(self, scenario: Scenario, submission: Submission) -> PrimaryScore:
        truth = scenario.ground_truth
        if not isinstance(truth, RankedGroundTruth) or not isinstance(submission, RankedSubmission):
            return PrimaryScore(headline=0.0, notes="unsupported scenario or submission type")

        if truth.abstention_is_correct:
            correct = bool(submission.abstained)
            return PrimaryScore(
                headline=1.0 if correct else 0.0,
                components={"correct_abstention": float(correct)},
                notes="the medicine is not on record, so the queue cannot be triaged",
            )

        if submission.abstained:
            return PrimaryScore(
                headline=0.0,
                components={"over_abstention": 1.0},
                notes="declined a queue the record supports triaging",
            )

        if not submission.items:
            return PrimaryScore(headline=0.0, components={"empty": 1.0}, notes="escalated nothing")

        discovery = ranking.average_precision(submission.ordered_ids, truth.positives)
        # Review burden, priced by how much each false escalation actually costs.
        burden = ranking.negative_burden(
            submission, truth.negatives, truth.negative_costs, listing_floor=LISTING_FLOOR
        )
        restraint = 1.0 - burden
        core = _harmonic(discovery, restraint)

        confidences, outcomes = ranking.outcomes_for_calibration(submission, truth.positives)
        report = calibration.score(confidences, outcomes)
        cal = _calibration_credit(report)

        headline = W_CORE * core + W_CALIBRATION * cal

        # Diagnostic: how much of the burden came from serious events specifically. Not
        # scored, but it is what tells a reader whether a model is broadly trigger-happy or
        # specifically drawn to escalating alarming-sounding terms.
        listed = set(submission.ordered_ids)
        serious_negatives = {e for e in truth.negatives if truth.cost_of(e) > 1.0}
        serious_taken = (
            len(listed & serious_negatives) / len(serious_negatives) if serious_negatives else 0.0
        )

        return PrimaryScore(
            headline=min(1.0, max(0.0, headline)),
            components={
                "discovery_ap": discovery,
                "review_restraint": restraint,
                "core": core,
                "calibration_skill": cal,
                "brier": report.brier,
                "overconfidence": report.overconfidence,
                "serious_false_escalation_rate": serious_taken,
                "n_items": float(len(submission.items)),
            },
        )

    def proxy_score(self, scenario: Scenario, submission: Submission) -> float | None:
        """Recall on the signals that held up, ignoring everything escalated alongside them.

        The metric a pharmacovigilance system is usually defended with, and the one that
        cannot see alert fatigue. `escalate_everything` scores 1.0 on it.
        """
        truth = scenario.ground_truth
        if not isinstance(truth, RankedGroundTruth) or not isinstance(submission, RankedSubmission):
            return None
        if truth.abstention_is_correct:
            return None
        return ranking.recall_at_any(submission, truth.positives)

    def verify_claim(self, scenario: Scenario, claim: str) -> ClaimVerdict:
        return self._snapshot.verify_claim(scenario.metadata.get("drug"), claim)

    # ---- baselines ---------------------------------------------------------------

    def baselines(self) -> list[Baseline]:
        return [
            Baseline("noop", "Escalates nothing. The floor.", _noop, role="floor"),
            Baseline(
                "always_abstain",
                "Declines every queue. Reveals whether the scenario mix rewards hedging.",
                _always_abstain,
                role="floor",
            ),
            Baseline(
                "prr_ranking",
                "Escalates the strongest disproportionality signals and stops. The standard "
                "method, and a genuinely hard line for a model to beat.",
                self._prr_ranking,
                role="reference",
            ),
            Baseline(
                "escalate_everything",
                "Escalates the entire queue at hedged confidence. Written to max out the "
                "recall proxy while being the alert-fatigue policy, so the gap between the "
                "usual metric and the real one is demonstrable rather than asserted.",
                self._escalate_everything,
                role="adversarial",
            ),
        ]

    def _prr_ranking(self, scenario: Scenario) -> RankedSubmission:
        """Rank by pre-cutoff reporting ratio, escalate above a stricter threshold, stop.

        A real reference rather than a strawman. Ranking by disproportionality is what
        signal detection actually does, and the only judgement added here is a cutoff, which
        is what an analyst with a finite week adds too.
        """
        queue = self._queue_for(scenario)
        if queue is None:
            return RankedSubmission()
        chosen = [c for c in queue.candidates if c.prr_pre >= REFERENCE_PRR]
        chosen.sort(key=lambda c: (-c.prr_pre, c.event))
        return RankedSubmission(
            items=[
                RankedItem(
                    id=candidate.event,
                    # Deliberately modest. Most disproportionate pairs do not hold up, so a
                    # baseline that stated high confidence would be badly calibrated and the
                    # comparison would flatter any model that merely hedged.
                    confidence=0.45 if candidate.prr_pre >= 5.0 else 0.3,
                    supporting_claims=[
                        f"prr_at_least:{candidate.event}:{REFERENCE_PRR}",
                        f"cases_at_least:{candidate.event}:{candidate.cases_pre}",
                    ],
                )
                for candidate in chosen[:REFERENCE_MAX_ITEMS]
            ]
        )

    def _escalate_everything(self, scenario: Scenario) -> RankedSubmission:
        """Escalate the whole queue. The alert-fatigue policy, shipped so it can be measured.

        Against recall on real signals this is unbeatable, because escalating everything
        guarantees the real ones are in the list. Against the real score it collapses:
        average precision punishes burying them among the pairs that did not hold up, the
        restraint term charges for every one of those weighted by what reviewing it costs,
        and the calibration term charges for asserting a probability on all of them.

        If a change to the scoring ever lets this policy score well, that change broke the
        environment, and a test fails.
        """
        queue = self._queue_for(scenario)
        if queue is None:
            return RankedSubmission()
        return RankedSubmission(
            items=[
                RankedItem(
                    id=candidate.event,
                    confidence=0.5,
                    supporting_claims=[f"cases_at_least:{candidate.event}:{candidate.cases_pre}"],
                )
                for candidate in queue.candidates
            ]
        )


def _noop(scenario: Scenario) -> RankedSubmission:
    return RankedSubmission()


def _always_abstain(scenario: Scenario) -> RankedSubmission:
    return RankedSubmission(abstained=True, abstention_reason="baseline: always declines")
