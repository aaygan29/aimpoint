"""The task families for biotool_drift.

Each family module exposes a uniform interface so the environment can treat them
identically: ``FAMILY_ID``, ``TASK`` and ``CONTRACT`` (prompt text), ``generate(seed, n)``
(input records), ``oracle(record)`` (the correct answer), ``metamorphic(seed)`` (pairs whose
correct answers are equal), and ``ORACLE_SOURCE`` / ``REFERENCE_SOURCE`` (module strings for
the oracle and the naive-buggy reference baselines).
"""

from __future__ import annotations

from . import confidence_field, coord_extract, multichain_dist, strand_cds

FAMILIES = {m.FAMILY_ID: m for m in (coord_extract, strand_cds, multichain_dist, confidence_field)}

__all__ = ["FAMILIES"]
