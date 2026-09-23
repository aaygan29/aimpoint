"""Shared helpers for biotool_drift: a deterministic PRNG, sequence utilities, and the
generic sandboxed executor for a submitted ``solve`` function.

Kept self-contained (stdlib only, no cross-environment imports) so the environment folder
can be copied, reviewed, or deleted as a unit, the same property the rest of the repo has.
The executor mirrors screen_debug's: in-process by default for CI speed, subprocess isolation
opt-in via ``AIMPOINT_BIOTOOL_EXEC=subprocess`` for untrusted-model runs. Neither is a
hardened sandbox; production use should run inside the Inspect sandbox or a network-free
container. Tracked in the environment's known limits.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ALPHABET = "ACGT"
EXEC_MODE = os.environ.get("AIMPOINT_BIOTOOL_EXEC", "inprocess")

# Standard genetic code, DNA codons -> single-letter amino acid, "*" for stop.
_CODON_TABLE = {
    "TTT": "F",
    "TTC": "F",
    "TTA": "L",
    "TTG": "L",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "ATG": "M",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "*",
    "TAG": "*",
    "CAT": "H",
    "CAC": "H",
    "CAA": "Q",
    "CAG": "Q",
    "AAT": "N",
    "AAC": "N",
    "AAA": "K",
    "AAG": "K",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "TGT": "C",
    "TGC": "C",
    "TGA": "*",
    "TGG": "W",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "AGT": "S",
    "AGC": "S",
    "AGA": "R",
    "AGG": "R",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
}


def sub_seed(seed: int, tag: str) -> int:
    h = hashlib.blake2b(f"{seed}:{tag}".encode(), digest_size=8)
    return int.from_bytes(h.digest(), "big")


class Rng:
    """splitmix64: reproducible across machines and Python versions."""

    def __init__(self, seed: int) -> None:
        self._state = seed & ((1 << 64) - 1)

    def _next(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & ((1 << 64) - 1)
        return z ^ (z >> 31)

    def randint(self, lo: int, hi: int) -> int:
        return lo + self._next() % (hi - lo + 1)

    def choice(self, seq):
        return seq[self._next() % len(seq)]


def rand_dna(rng: Rng, n: int) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(n))


def revcomp(seq: str) -> str:
    table = {"A": "T", "T": "A", "G": "C", "C": "G"}
    return "".join(table.get(b, "N") for b in reversed(seq.upper()))


def translate(seq: str) -> str:
    """Translate a nucleotide sequence in frame 0 until the first stop (stop excluded)."""
    protein = []
    for i in range(0, len(seq) - len(seq) % 3, 3):
        aa = _CODON_TABLE.get(seq[i : i + 3].upper(), "X")
        if aa == "*":
            break
        protein.append(aa)
    return "".join(protein)


# --- generic sandboxed execution of a submitted `solve(record)` -------------------------

_DRIVER = """\
import json, importlib.util, sys
spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
records = json.load(open(sys.argv[2]))
out = []
for r in records:
    try:
        v = mod.solve(r)
        json.dumps(v)  # ensure serialisable; non-serialisable -> error -> None
        out.append(v)
    except Exception:
        out.append(None)
print(json.dumps(out))
"""


class _Timeout(Exception):
    pass


def run_solve(source: str, records: list[dict], timeout: float = 25.0) -> list:
    """Execute a submitted module's ``solve(record)`` over `records`.

    Returns one output per record; a crash, timeout, or non-serialisable result yields
    ``None`` for that record. The function never sees the expected answers.
    """
    if EXEC_MODE != "subprocess":
        return _run_inprocess(source, records, timeout)
    return _run_subprocess(source, records, timeout)


def _run_inprocess(source: str, records: list[dict], timeout: float) -> list:
    n = len(records)
    ns: dict = {}
    handler_set = False
    if hasattr(signal, "SIGALRM"):
        try:

            def _raise(_s, _f):
                raise _Timeout

            signal.signal(signal.SIGALRM, _raise)
            signal.setitimer(signal.ITIMER_REAL, timeout)
            handler_set = True
        except (ValueError, OSError):
            handler_set = False
    try:
        exec(source, ns)
        solve = ns.get("solve")
        if not callable(solve):
            return [None] * n
        out = []
        for r in records:
            try:
                v = solve(json.loads(json.dumps(r)))  # hand solve a private copy
                json.dumps(v)
                out.append(v)
            except Exception:
                out.append(None)
        return out
    except (_Timeout, Exception):
        return [None] * n
    finally:
        if handler_set:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)


def _run_subprocess(source: str, records: list[dict], timeout: float) -> list:
    n = len(records)

    def _limit():
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (int(timeout), int(timeout)))
        except Exception:
            pass

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "candidate.py"
        src.write_text(source)
        data = tmp_path / "records.json"
        data.write_text(json.dumps(records))
        driver = tmp_path / "driver.py"
        driver.write_text(_DRIVER)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(driver), str(src), str(data)],
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=_limit,
                cwd=tmp,
            )
        except (subprocess.TimeoutExpired, OSError):
            return [None] * n
        if proc.returncode != 0:
            return [None] * n
        try:
            result = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return [None] * n
        if not isinstance(result, list) or len(result) != n:
            return [None] * n
        return result
