"""Confidence-output drift: mean pLDDT over a residue range.

The silent bugs this targets are reading the wrong field from a structure-prediction
confidence output (returning ptm/iptm instead of a pLDDT summary) and off-by-one indexing
of a 1-based residue range into a 0-based per-residue array. The output layout mimics a
Boltz / AlphaFold confidence JSON with several similarly named scalars alongside the
per-residue plddt list.
"""

from __future__ import annotations

from ..common import Rng, sub_seed

FAMILY_ID = "confidence_field"

TASK = (
    "Given a structure-prediction confidence record, return the mean pLDDT over the "
    "inclusive 1-based residue range [start, end], rounded to 3 decimals. Use the per-residue "
    "'plddt' array; ignore the scalar ptm/iptm fields."
)

CONTRACT = (
    "def solve(record) -> float\n"
    "record = {\n"
    "    'plddt': [float, ...],  # per-residue, index 0 is residue 1\n"
    "    'ptm': float, 'iptm': float,\n"
    "    'start': int, 'end': int,  # 1-based inclusive residue range\n"
    "}\n"
    "Return the mean pLDDT over the range, rounded to 3 decimals."
)

ORACLE_SOURCE = """\
def solve(record):
    p = record["plddt"]
    s, e = record["start"], record["end"]
    window = p[s-1:e]
    return round(sum(window)/len(window), 3)
"""

# Naive: treat the 1-based range as 0-based, slicing p[start:end]. Off by one at the start
# and short by one at the end. A very common confidence-array indexing slip.
REFERENCE_SOURCE = """\
def solve(record):
    p = record["plddt"]
    window = p[record["start"]:record["end"]]
    return round(sum(window)/len(window), 3)
"""


def oracle(inp: dict) -> float:
    p = inp["plddt"]
    window = p[inp["start"] - 1 : inp["end"]]
    return round(sum(window) / len(window), 3)


def _plddt(rng: Rng, n: int) -> list[float]:
    return [rng.randint(200, 990) / 10.0 for _ in range(n)]


def _record(rng: Rng, plddt: list[float], s: int, e: int) -> dict:
    return {
        "plddt": plddt,
        "ptm": rng.randint(0, 1000) / 1000.0,
        "iptm": rng.randint(0, 1000) / 1000.0,
        "start": s,
        "end": e,
    }


def generate(seed: int, n: int) -> list[dict]:
    rng = Rng(sub_seed(seed, "conf"))
    out = []
    for _ in range(n):
        L = rng.randint(20, 40)
        plddt = _plddt(rng, L)
        s = rng.randint(1, L - 5)
        e = rng.randint(s + 1, L)
        out.append(_record(rng, plddt, s, e))
    return out


def metamorphic(seed: int) -> list[tuple[dict, dict]]:
    """Two records whose plddt values are identical WITHIN [start, end] but differ outside
    it (and in ptm/iptm) must give the same mean. This catches both a wrong-field answer
    (ptm differs) and an off-by-one that reaches outside the range."""
    rng = Rng(sub_seed(seed, "conf_meta"))
    pairs = []
    for _ in range(8):
        L = rng.randint(20, 40)
        base = _plddt(rng, L)
        s = rng.randint(2, L - 6)
        e = rng.randint(s + 1, L - 1)
        # Second record: same values in [s-1:e], different everywhere else.
        other = _plddt(rng, L)
        for i in range(s - 1, e):
            other[i] = base[i]
        pairs.append((_record(rng, base, s, e), _record(rng, other, s, e)))
    return pairs
