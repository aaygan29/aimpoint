"""Scoring the metamorphic battery.

The cases themselves are built in ``data.build_metamorphic``. This module turns a
candidate's outputs on those cases into a per-check pass fraction. Kept separate so the
invariant set is declared and scored in one obvious place rather than hand-rolled inside
the primary scorer, which is the harness support the execution track needs.
"""

from __future__ import annotations

from .data import MetamorphicCase


def score(cases: list[MetamorphicCase], outputs: list[bool | None]) -> dict[str, float]:
    """Return {check_name: pass_fraction} plus an ``overall`` mean over all cases.

    A ``None`` output (execution error) is a failure. Each case's expected outcome is the
    oracle's, so the reference screener passes every check by construction.
    """
    by_check: dict[str, list[bool]] = {}
    for case, out in zip(cases, outputs, strict=False):
        passed = out is not None and bool(out) == case.expected
        by_check.setdefault(case.check, []).append(passed)
    result = {check: sum(v) / len(v) for check, v in by_check.items()}
    # Equal weight per invariant, not per case, so a defect that breaks one invariant is not
    # diluted by the many cases of the invariants it happens to leave intact. This is what
    # makes the battery discriminate a one-line bug from a correct fix.
    result["overall"] = sum(result.values()) / len(result) if result else 0.0
    return result
