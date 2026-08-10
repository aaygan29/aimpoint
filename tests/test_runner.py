"""The entry point, exercised the way a user reaches it.

These exist because of a bug that made `aimpoint run-env` fail on a clean install while the
rest of the suite stayed green. Every other test drove `inspect_eval` directly, so nothing
covered the one function the CLI actually calls, and the failure surfaced only when the
repository was cloned fresh and run the way a stranger would run it.

The lesson generalises past the specific bug: a suite that reaches past its own entry point
can be entirely green on a product nobody can start.
"""

from __future__ import annotations

import json

from inspect_ai.model import ModelOutput

from aimpoint.core.env import Split
from aimpoint.core.registry import load_env
from aimpoint.runner import run, write_card
from tests.conftest import MOCK


def _script() -> list[ModelOutput]:
    """Enough scripted submissions to carry the limited scenario set to termination."""
    item = {"id": "SOMETHING", "confidence": 0.5, "supporting_claims": ["x"]}
    return [ModelOutput.for_tool_call(MOCK, "submit", {"items": [item]}) for _ in range(40)]


def _run(tmp_path, **kwargs):
    return run(
        load_env("target_triage"),
        model=MOCK,
        split=Split.DEV,
        log_dir=str(tmp_path / "logs"),
        model_args={"custom_outputs": _script()},
        **kwargs,
    )


def test_run_completes_against_a_mock_model(tmp_path):
    """The path the CLI takes, end to end.

    One replicate over two scenarios is enough. The point is that the call into Inspect is
    well formed and a result comes back, not that the numbers mean anything.
    """
    result = _run(tmp_path, replicates=1, limit=2)

    assert result.env_id == "target_triage"
    assert result.aggregate.per_replicate, "no replicate scores came back"
    assert result.aggregate.baselines, "no baselines to compare the score against"


def test_run_card_serialises(tmp_path):
    """A card that cannot be written is a result nobody can publish or compare."""
    result = _run(tmp_path, replicates=1, limit=1)
    path = write_card(result, tmp_path / "card.json")
    reloaded = json.loads(path.read_text())

    assert reloaded["env_id"] == "target_triage"
    assert "baselines" in reloaded
    assert "warnings" in reloaded


def test_below_three_replicates_suppresses_the_headline(tmp_path):
    """The repository's own rule, enforced where it is claimed rather than only documented.

    A single run reports run-to-run variance as though it were a property of the model, so
    the harness refuses to publish a headline for one. If that silently stopped holding, the
    number most likely to be quoted would become the one least entitled to be.
    """
    card = _run(tmp_path, replicates=1, limit=1).as_card()

    assert card["headline"] is None
    assert card["headline_suppressed"]
