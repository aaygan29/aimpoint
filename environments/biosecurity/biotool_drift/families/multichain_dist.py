"""Multi-chain drift: distance between two residues' CA atoms in a structure.

The silent bug: identifying a residue by ``resSeq`` alone. Residue numbers repeat across
chains, so ignoring the chain id grabs the wrong atom whenever a number collides. The
correct key is (chain, resSeq).
"""

from __future__ import annotations

from ..common import Rng, sub_seed

FAMILY_ID = "multichain_dist"

TASK = (
    "Given a structure (a list of atom records) and two residue selectors, return the "
    "Euclidean distance between the two residues' CA atoms, rounded to 2 decimals. A residue "
    "is identified by BOTH its chain and its resSeq; residue numbers repeat across chains."
)

CONTRACT = (
    "def solve(record) -> float\n"
    "record = {\n"
    "    'atoms': [ {'chain': str, 'resSeq': int, 'atom': str, 'x': float, 'y': float, "
    "'z': float}, ... ],\n"
    "    'a': {'chain': str, 'resSeq': int},\n"
    "    'b': {'chain': str, 'resSeq': int},\n"
    "}\n"
    "Return the CA-CA distance rounded to 2 decimals."
)

ORACLE_SOURCE = """\
def _ca(atoms, sel):
    for at in atoms:
        if at["chain"] == sel["chain"] and at["resSeq"] == sel["resSeq"] and at["atom"] == "CA":
            return at
    return None

def solve(record):
    a = _ca(record["atoms"], record["a"])
    b = _ca(record["atoms"], record["b"])
    d = ((a["x"]-b["x"])**2 + (a["y"]-b["y"])**2 + (a["z"]-b["z"])**2) ** 0.5
    return round(d, 2)
"""

# Naive: match on resSeq only, ignoring chain. Correct until a residue number collides
# across chains, which the generator makes happen about half the time.
REFERENCE_SOURCE = """\
def _ca(atoms, sel):
    for at in atoms:
        if at["resSeq"] == sel["resSeq"] and at["atom"] == "CA":
            return at
    return None

def solve(record):
    a = _ca(record["atoms"], record["a"])
    b = _ca(record["atoms"], record["b"])
    d = ((a["x"]-b["x"])**2 + (a["y"]-b["y"])**2 + (a["z"]-b["z"])**2) ** 0.5
    return round(d, 2)
"""


def _ca(atoms: list[dict], chain: str, res: int) -> dict | None:
    for at in atoms:
        if at["chain"] == chain and at["resSeq"] == res and at["atom"] == "CA":
            return at
    return None


def oracle(inp: dict) -> float:
    a = _ca(inp["atoms"], inp["a"]["chain"], inp["a"]["resSeq"])
    b = _ca(inp["atoms"], inp["b"]["chain"], inp["b"]["resSeq"])
    d = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2) ** 0.5
    return round(d, 2)


def _atom(rng: Rng, chain: str, res: int) -> dict:
    return {
        "chain": chain,
        "resSeq": res,
        "atom": "CA",
        "x": rng.randint(0, 5000) / 100.0,
        "y": rng.randint(0, 5000) / 100.0,
        "z": rng.randint(0, 5000) / 100.0,
    }


def _structure(rng: Rng, collide: bool) -> dict:
    # Chains use non-overlapping numbering by default (A: 1.., B: 101..), so a chain-ignoring
    # lookup is correct until a colliding decoy is planted.
    atoms = []
    for res in range(1, rng.randint(5, 8)):
        atoms.append(_atom(rng, "A", res))
    for res in range(101, 100 + rng.randint(5, 8)):
        atoms.append(_atom(rng, "B", res))
    target_res = 101  # a chain B residue
    if collide:
        # Plant a chain A atom with the same resSeq, before chain B's, so a chain-ignoring
        # lookup grabs the wrong (chain A) atom.
        atoms.insert(0, _atom(rng, "A", target_res))
    a_sel = {"chain": "A", "resSeq": 1}
    b_sel = {"chain": "B", "resSeq": target_res}
    return {"atoms": atoms, "a": a_sel, "b": b_sel}


def generate(seed: int, n: int) -> list[dict]:
    rng = Rng(sub_seed(seed, "chain"))
    return [_structure(rng, collide=(k % 2 == 0)) for k in range(n)]


def metamorphic(seed: int) -> list[tuple[dict, dict]]:
    """A structure and the same structure with a decoy atom (same resSeq, other chain)
    inserted must give the same CA-CA distance. A chain-ignoring candidate grabs the decoy
    and returns a different value, so the equality fails."""
    rng = Rng(sub_seed(seed, "chain_meta"))
    pairs = []
    for _ in range(8):
        clean = _structure(rng, collide=False)
        decoyed = {
            "atoms": [_atom(rng, "A", clean["b"]["resSeq"]), *clean["atoms"]],
            "a": clean["a"],
            "b": clean["b"],
        }
        pairs.append((clean, decoyed))
    return pairs
