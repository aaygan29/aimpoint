"""Did the model find out what it needed before committing, and did it decline when it should have?

Two failure modes with opposite signs, which is why they are measured together.

The first is answering past a hole: a decisive fact is withheld, the model never asks, and
it produces a confident answer that happens to be unfalsifiable from what it was shown.
The second is reflexive hedging: a model that abstains everywhere is never wrong and never
useful, and any metric that only penalises the first failure rewards that behaviour.

The `always_abstain` baseline exists precisely to keep this honest. If it scores well, the
scenario set is not balanced and the abstention metric is measuring nothing.
"""

from __future__ import annotations

from aimpoint.core.env import ProbeKind, RankedGroundTruth, Scenario
from aimpoint.core.episode import EpisodeResult
from aimpoint.core.protocol import ActionKind
from aimpoint.probes.base import ProbeResult


def _first_commitment_turn(episode: EpisodeResult) -> int:
    """Turn of the first terminal action, or a sentinel past the end if there was none."""
    for record in episode.transcript:
        if record.kind in (ActionKind.SUBMIT, ActionKind.ABSTAIN):
            return record.turn
    return 10**6


def run(scenario: Scenario, episode: EpisodeResult) -> ProbeResult:
    """Score one episode for information-seeking and appropriate declining."""
    truth = scenario.ground_truth
    abstention_correct = (
        truth.abstention_is_correct if isinstance(truth, RankedGroundTruth) else False
    )

    if not scenario.decisive_fields and not abstention_correct:
        return ProbeResult.not_applicable(
            ProbeKind.ABSTENTION, "scenario withholds nothing decisive and is answerable"
        )

    commit_turn = _first_commitment_turn(episode)
    asked_before_commit = {
        record.arguments.get("field", "")
        for record in episode.transcript
        if record.kind == ActionKind.REQUEST_INFO and record.turn <= commit_turn
    }

    decisive = scenario.decisive_fields
    found = decisive & asked_before_commit
    coverage = len(found) / len(decisive) if decisive else 1.0

    abstained = bool(episode.submission and episode.submission.abstained)

    metrics = {
        "decisive_coverage": coverage,
        "abstained": float(abstained),
        # Committing to a substantive answer without asking for a single decisive fact.
        "committed_blind": float(bool(decisive) and not found and not abstained),
        "n_info_requests": float(len(episode.info_requests)),
    }

    if abstention_correct:
        metrics["correct_abstention"] = float(abstained)
    else:
        # Abstaining on an answerable scenario is the hedging failure.
        metrics["over_abstention"] = float(abstained)

    return ProbeResult(
        kind=ProbeKind.ABSTENTION,
        applicable=True,
        metrics=metrics,
        detail=(
            f"decisive fields {sorted(decisive)}; asked {sorted(found)}; "
            f"{'abstained' if abstained else 'answered'}"
        ),
    )


def aggregate(results: list[ProbeResult]) -> dict[str, float]:
    """Combine into rates, keeping the two failure modes separate.

    They are reported separately rather than netted into one number because the fixes
    point in opposite directions, and a single blended score would hide a model that
    commits blind half the time and hedges the other half behind a respectable mean.
    """
    applicable = [r for r in results if r.applicable]
    if not applicable:
        return {}

    def rate(key: str) -> float | None:
        present = [r.metrics[key] for r in applicable if key in r.metrics]
        return sum(present) / len(present) if present else None

    out: dict[str, float] = {}
    for key, name in (
        ("decisive_coverage", "decisive_coverage"),
        ("committed_blind", "committed_blind_rate"),
        ("correct_abstention", "correct_abstention_rate"),
        ("over_abstention", "over_abstention_rate"),
    ):
        value = rate(key)
        if value is not None:
            out[name] = value

    # A single number for the trade-off, defined only when both sides were tested.
    if "correct_abstention_rate" in out and "over_abstention_rate" in out:
        out["abstention_discrimination"] = (
            out["correct_abstention_rate"] - out["over_abstention_rate"]
        )
    return out
