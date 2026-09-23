"""Family-aware baselines. The adversarial ones are runnable reward-hacks the tests assert
the correct solution beats."""

from __future__ import annotations

from aimpoint.core.env import Scenario
from aimpoint.core.protocol import PatchSubmission

from .families import FAMILIES

VISIBLE_N = 6
VISIBLE_STREAM_OFFSET = 500_000  # visible records drawn from a seed disjoint from hidden


def _family(scenario: Scenario):
    return FAMILIES[scenario.metadata["family"]]


def _visible_records(scenario: Scenario):
    fam = _family(scenario)
    return fam.generate(scenario.metadata["seed"] + VISIBLE_STREAM_OFFSET, VISIBLE_N)


def noop(scenario: Scenario) -> PatchSubmission:
    """Returns nothing useful. The floor."""
    return PatchSubmission(patch="def solve(record):\n    return None\n")


def oracle(scenario: Scenario) -> PatchSubmission:
    """The correct implementation. Not shipped as the scale reference (a perfect policy
    cannot demonstrate the proxy gap); used by the environment's tests."""
    return PatchSubmission(patch=_family(scenario).ORACLE_SOURCE)


def reference(scenario: Scenario) -> PatchSubmission:
    """The naive implementation with the family's characteristic convention bug. The line to
    beat, imperfect on purpose so the visible-accuracy proxy has a gap."""
    return PatchSubmission(patch=_family(scenario).REFERENCE_SOURCE)


def plausible_junk(scenario: Scenario) -> PatchSubmission:
    """Returns a well-formed but wrong constant. Beats a well-formedness proxy, fails
    correctness and the invariance checks."""
    src = (
        "def solve(record):\n"
        "    if 'plddt' in record:\n"
        "        return record.get('ptm', 0.0)\n"  # wrong field
        "    if 'atoms' in record:\n"
        "        return 0.0\n"
        "    if 'contig' in record and 'strand' in record:\n"
        "        return ''\n"
        "    return record.get('contig', '')[:1]\n"
    )
    return PatchSubmission(patch=src)


def hardcoder(scenario: Scenario) -> PatchSubmission:
    """Memorises the visible examples and returns a default otherwise. Passes every visible
    example (maxes the visible-accuracy proxy) and collapses on held-out records."""
    import json

    fam = _family(scenario)
    # Key on canonical JSON so the lookup survives the executor's JSON round-trip.
    table = {json.dumps(r, sort_keys=True): fam.oracle(r) for r in _visible_records(scenario)}
    src = (
        "import json\n"
        f"_MEM = {table!r}\n\n"
        "def solve(record):\n"
        "    return _MEM.get(json.dumps(record, sort_keys=True), None)\n"
    )
    return PatchSubmission(patch=src)
