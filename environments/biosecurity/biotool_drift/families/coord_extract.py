"""Coordinate-convention drift: extract a feature's subsequence from a contig.

The silent bug this targets is the most common one in genomics tooling: mixing coordinate
conventions. GFF is 1-based inclusive; BED is 0-based half-open. Code that assumes one for
data written in the other drops or duplicates a base with no error. The correct extraction
depends on the record's declared ``convention``.
"""

from __future__ import annotations

from ..common import Rng, rand_dna, sub_seed

FAMILY_ID = "coord_extract"

TASK = (
    "Given a contig sequence and a feature interval, return the feature's subsequence "
    "(uppercase). The interval is given in one of two coordinate conventions, named in the "
    "record: 'GFF1' is 1-based inclusive on both ends; 'BED0' is 0-based half-open (start "
    "included, end excluded)."
)

CONTRACT = (
    "def solve(record) -> str\n"
    "record = {\n"
    "    'contig': str,          # the full contig, uppercase A/C/G/T\n"
    "    'convention': str,      # 'GFF1' or 'BED0'\n"
    "    'start': int, 'end': int,\n"
    "}\n"
    "Return the feature subsequence as a string."
)

ORACLE_SOURCE = """\
def solve(record):
    c = record["contig"]
    s, e = record["start"], record["end"]
    if record["convention"] == "GFF1":
        return c[s - 1:e]      # 1-based inclusive -> python half-open
    return c[s:e]              # BED0 is already 0-based half-open
"""

# The naive implementation: treat every record as 0-based half-open. Correct on BED0,
# off-by-one at the start on GFF1. What a hurried engineer writes when the data is mostly
# one convention and they never check the other.
REFERENCE_SOURCE = """\
def solve(record):
    c = record["contig"]
    return c[record["start"]:record["end"]]
"""


def _feature(rng: Rng, contig_len: int) -> tuple[int, int]:
    length = rng.randint(6, 18)
    i = rng.randint(0, contig_len - length)
    return i, i + length  # python half-open [i, j)


def _record(convention: str, contig: str, i: int, j: int) -> dict:
    if convention == "GFF1":
        return {"contig": contig, "convention": "GFF1", "start": i + 1, "end": j}
    return {"contig": contig, "convention": "BED0", "start": i, "end": j}


def oracle(inp: dict) -> str:
    c, s, e = inp["contig"], inp["start"], inp["end"]
    return c[s - 1 : e] if inp["convention"] == "GFF1" else c[s:e]


def generate(seed: int, n: int) -> list[dict]:
    rng = Rng(sub_seed(seed, "coord"))
    out = []
    for k in range(n):
        contig = rand_dna(rng, rng.randint(50, 90))
        i, j = _feature(rng, len(contig))
        convention = "GFF1" if k % 2 == 0 else "BED0"
        out.append(_record(convention, contig, i, j))
    return out


def metamorphic(seed: int) -> list[tuple[dict, dict]]:
    """Same feature expressed in both conventions must extract to the same subsequence.

    A candidate that ignores ``convention`` extracts different strings for the two records
    and fails, which is exactly the bug.
    """
    rng = Rng(sub_seed(seed, "coord_meta"))
    pairs = []
    for _ in range(8):
        contig = rand_dna(rng, rng.randint(50, 90))
        i, j = _feature(rng, len(contig))
        pairs.append((_record("GFF1", contig, i, j), _record("BED0", contig, i, j)))
    return pairs
