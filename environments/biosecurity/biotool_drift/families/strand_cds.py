"""Strand drift: translate a coding feature, respecting strand.

The silent bug: extracting a minus-strand feature without reverse-complementing it first, so
the translation is of the wrong strand. Coordinates are always given on the forward contig
(GFF convention); the ``strand`` field says which strand the feature is read from.
"""

from __future__ import annotations

from ..common import Rng, rand_dna, revcomp, sub_seed, translate

FAMILY_ID = "strand_cds"

TASK = (
    "Given a contig and a coding feature (1-based inclusive GFF coordinates on the forward "
    "contig) with a strand, return the translated protein (single-letter, frame 0, stopping "
    "before the first stop codon). For a '-' strand feature, translate the reverse "
    "complement of the extracted region."
)

CONTRACT = (
    "def solve(record) -> str\n"
    "record = {\n"
    "    'contig': str,          # forward strand, uppercase A/C/G/T\n"
    "    'start': int, 'end': int,  # 1-based inclusive\n"
    "    'strand': str,          # '+' or '-'\n"
    "}\n"
    "Return the protein string."
)

ORACLE_SOURCE = """\
_CODON = {
 "TTT":"F","TTC":"F","TTA":"L","TTG":"L","CTT":"L","CTC":"L","CTA":"L","CTG":"L",
 "ATT":"I","ATC":"I","ATA":"I","ATG":"M","GTT":"V","GTC":"V","GTA":"V","GTG":"V",
 "TCT":"S","TCC":"S","TCA":"S","TCG":"S","CCT":"P","CCC":"P","CCA":"P","CCG":"P",
 "ACT":"T","ACC":"T","ACA":"T","ACG":"T","GCT":"A","GCC":"A","GCA":"A","GCG":"A",
 "TAT":"Y","TAC":"Y","TAA":"*","TAG":"*","CAT":"H","CAC":"H","CAA":"Q","CAG":"Q",
 "AAT":"N","AAC":"N","AAA":"K","AAG":"K","GAT":"D","GAC":"D","GAA":"E","GAG":"E",
 "TGT":"C","TGC":"C","TGA":"*","TGG":"W","CGT":"R","CGC":"R","CGA":"R","CGG":"R",
 "AGT":"S","AGC":"S","AGA":"R","AGG":"R","GGT":"G","GGC":"G","GGA":"G","GGG":"G"}

def _rc(s):
    t={"A":"T","T":"A","G":"C","C":"G"}
    return "".join(t.get(b,"N") for b in reversed(s))

def _tr(s):
    p=[]
    for i in range(0,len(s)-len(s)%3,3):
        aa=_CODON.get(s[i:i+3],"X")
        if aa=="*": break
        p.append(aa)
    return "".join(p)

def solve(record):
    sub = record["contig"][record["start"]-1:record["end"]]
    if record["strand"] == "-":
        sub = _rc(sub)
    return _tr(sub)
"""

# Naive: ignore strand, always translate the forward extraction. Correct on '+', wrong on
# '-'. The single most common strand bug.
REFERENCE_SOURCE = ORACLE_SOURCE.replace(
    '    if record["strand"] == "-":\n        sub = _rc(sub)\n', ""
)


def oracle(inp: dict) -> str:
    sub = inp["contig"][inp["start"] - 1 : inp["end"]]
    if inp["strand"] == "-":
        sub = revcomp(sub)
    return translate(sub)


def _record(contig: str, i: int, j: int, strand: str) -> dict:
    # i, j are python half-open; GFF 1-based inclusive is (i+1, j).
    return {"contig": contig, "start": i + 1, "end": j, "strand": strand}


def generate(seed: int, n: int) -> list[dict]:
    rng = Rng(sub_seed(seed, "strand"))
    out = []
    for k in range(n):
        contig = rand_dna(rng, rng.randint(60, 120))
        length = 3 * rng.randint(3, 8)
        i = rng.randint(0, len(contig) - length)
        strand = "+" if k % 2 == 0 else "-"
        out.append(_record(contig, i, i + length, strand))
    return out


def metamorphic(seed: int) -> list[tuple[dict, dict]]:
    """A '+' feature on a contig and the same feature as '-' on the reverse-complemented
    contig must translate to the same protein. A candidate that ignores strand fails."""
    rng = Rng(sub_seed(seed, "strand_meta"))
    pairs = []
    for _ in range(8):
        contig = rand_dna(rng, rng.randint(60, 120))
        length = 3 * rng.randint(3, 8)
        i = rng.randint(0, len(contig) - length)
        j = i + length
        rc = revcomp(contig)
        L = len(contig)
        plus = _record(contig, i, j, "+")
        minus = _record(rc, L - j, L - i, "-")  # mirrored coords on the reverse strand
        pairs.append((plus, minus))
    return pairs
