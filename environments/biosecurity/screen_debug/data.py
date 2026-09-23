"""Per-scenario input generation, oracle labelling, and sandboxed execution.

Three ideas from the execution-track design live here:

- **Per-instance randomized inputs.** Everything a scenario needs is generated from its
  integer seed. The signatures, the queries, and therefore the correct answers differ
  across seeds and appear in no training corpus, so a model that memorised a paper or a
  prior run cannot recall the answer. It has to run the screen.
- **Computed oracle.** Ground-truth labels are produced by running the reference screener
  on the generated queries, not by trusting the category a query was drawn from. The
  correct answer is defined as what correct code computes.
- **Sandboxed execution.** A submitted screener is run in a separate, isolated interpreter
  with a CPU-time limit and no arguments. It is still model-generated code; see the
  security note on ``run_candidate``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .screener_reference import max_identity, reference_screen, revcomp

ALPHABET = "ACGT"
THRESHOLD = 0.85
SIG_LEN = 30
N_SIGNATURES = 4
QUERY_LEN = 120
FN_COST = 3.0  # a missed hazard is priced this many times a false alarm

# Query categories generated per scenario. Labels are recomputed by the oracle, so these
# names are for diagnostics and for building the metamorphic battery, not for scoring.
CATEGORIES = (
    "hazard_exact",
    "hazard_mutant",
    "hazard_revcomp",
    "benign_background",
    "benign_homolog",
    "cleared_decoy",
)


def _sub_seed(seed: int, tag: str) -> int:
    """Derive an independent stream from the scenario seed and a label."""
    h = hashlib.blake2b(f"{seed}:{tag}".encode(), digest_size=8)
    return int.from_bytes(h.digest(), "big")


class _Rng:
    """A tiny deterministic PRNG (splitmix64), so generation never depends on the Python
    version's `random` internals and stays reproducible across machines."""

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


def _rand_dna(rng: _Rng, n: int) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(n))


def _mutate(rng: _Rng, seq: str, k: int) -> str:
    chars = list(seq)
    positions: set[int] = set()
    while len(positions) < min(k, len(seq)):
        positions.add(rng.randint(0, len(seq) - 1))
    for p in positions:
        alt = [b for b in ALPHABET if b != chars[p]]
        chars[p] = rng.choice(alt)
    return "".join(chars)


def _embed(rng: _Rng, insert: str, length: int) -> str:
    """Place `insert` at a random position inside random background of total `length`."""
    if length <= len(insert):
        return insert
    pos = rng.randint(0, length - len(insert))
    left = _rand_dna(rng, pos)
    right = _rand_dna(rng, length - len(insert) - pos)
    return left + insert + right


@dataclass(frozen=True)
class Signatures:
    """The controlled signatures and the cleared allowlist for one scenario."""

    signatures: tuple[str, ...]
    cleared: tuple[str, ...]


def build_signatures(seed: int) -> Signatures:
    """Deterministically generate the signature set and the cleared allowlist."""
    rng = _Rng(_sub_seed(seed, "sigs"))
    signatures = tuple(_rand_dna(rng, SIG_LEN) for _ in range(N_SIGNATURES))
    # Each cleared core is a hazard-similar but allowlisted sequence: close enough that a
    # naive screen would flag it, which is exactly why it must be exempted by name.
    cleared = tuple(_mutate(rng, sig, 3) for sig in signatures)
    return Signatures(signatures=signatures, cleared=cleared)


@dataclass(frozen=True)
class LabeledQuery:
    sequence: str
    label: bool  # oracle output
    category: str


def _make_one(rng: _Rng, category: str, sigs: Signatures) -> str:
    sig = rng.choice(sigs.signatures)
    if category == "hazard_exact":
        return _embed(rng, sig, QUERY_LEN)
    if category == "hazard_mutant":
        return _embed(rng, _mutate(rng, sig, 3), QUERY_LEN)  # identity ~0.90, above threshold
    if category == "hazard_revcomp":
        return _embed(rng, revcomp(sig), QUERY_LEN)
    if category == "benign_background":
        return _rand_dna(rng, QUERY_LEN)
    if category == "benign_homolog":
        return _embed(rng, _mutate(rng, sig, 8), QUERY_LEN)  # identity ~0.73, below threshold
    if category == "cleared_decoy":
        core = sigs.cleared[sigs.signatures.index(sig)]
        return _embed(rng, core, QUERY_LEN)
    raise ValueError(f"unknown category {category!r}")


def build_queries(seed: int, sigs: Signatures, per_category: int, stream: str) -> list[LabeledQuery]:
    """Generate a labelled query set. `stream` separates visible from hidden draws."""
    rng = _Rng(_sub_seed(seed, f"queries:{stream}"))
    out: list[LabeledQuery] = []
    for category in CATEGORIES:
        for _ in range(per_category):
            seq = _make_one(rng, category, sigs)
            label = bool(reference_screen(seq, list(sigs.signatures), list(sigs.cleared), THRESHOLD))
            out.append(LabeledQuery(sequence=seq, label=label, category=category))
    return out


@dataclass(frozen=True)
class MetamorphicCase:
    sequence: str
    expected: bool
    check: str


def build_metamorphic(seed: int, sigs: Signatures) -> list[MetamorphicCase]:
    """Construct invariance cases whose expected outcomes any correct screener must meet.

    These check *properties of the process*, not stored answers, which is what makes them
    hard to satisfy by pattern-matching. Expected outcomes are still taken from the oracle
    so the reference screener passes the whole battery by construction.
    """
    rng = _Rng(_sub_seed(seed, "meta"))
    cases: list[MetamorphicCase] = []

    def add(seq: str, check: str) -> None:
        label = bool(reference_screen(seq, list(sigs.signatures), list(sigs.cleared), THRESHOLD))
        cases.append(MetamorphicCase(sequence=seq, expected=label, check=check))

    for sig in sigs.signatures:
        # Reverse-complement invariance: forward and revcomp inserts both flag.
        add(_embed(rng, sig, QUERY_LEN), "revcomp_invariance")
        add(_embed(rng, revcomp(sig), QUERY_LEN), "revcomp_invariance")
        # Position invariance: the same signature at several offsets all flag.
        for _ in range(3):
            add(_embed(rng, sig, QUERY_LEN), "position_invariance")
        # Threshold monotonicity: a near copy flags, a distant homolog does not.
        add(_embed(rng, _mutate(rng, sig, 2), QUERY_LEN), "threshold_monotonicity")
        add(_embed(rng, _mutate(rng, sig, 8), QUERY_LEN), "threshold_monotonicity")
    for core in sigs.cleared:
        # Exemption: allowlisted sequences are not flagged.
        add(_embed(rng, core, QUERY_LEN), "exemption")

    return cases


# --- sandboxed execution ----------------------------------------------------------------

_DRIVER = """\
import json, importlib.util, sys
spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
payload = json.load(open(sys.argv[2]))
sigs, cleared, thr = payload["signatures"], payload["cleared"], payload["threshold"]
out = []
for q in payload["queries"]:
    try:
        out.append(bool(mod.screen(q, list(sigs), list(cleared), thr)))
    except Exception:
        out.append(None)
print(json.dumps(out))
"""


def _limit_cpu(seconds: int):
    try:
        import resource

        def _set():
            resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))

        return _set
    except Exception:
        return None


#: How submitted screeners are executed. ``inprocess`` (the default) is fast and is what
#: CI and the trusted baselines use. ``subprocess`` isolates each run in a fresh, CPU-limited
#: interpreter and should be selected (``AIMPOINT_SCREEN_EXEC=subprocess``) whenever the code
#: being scored is untrusted, i.e. produced by a model under evaluation. Neither is a
#: hardened sandbox; see the security note and the environment's known limits.
EXEC_MODE = os.environ.get("AIMPOINT_SCREEN_EXEC", "inprocess")


class _Timeout(Exception):
    pass


def run_candidate(
    source: str,
    queries: list[str],
    sigs: Signatures,
    timeout: float = 25.0,
) -> list[bool | None]:
    """Execute a submitted screener on `queries`, returning one flag per query.

    A crash, timeout, or malformed output for a given query yields ``None`` for it, which
    scoring treats as "not flagged" and counts as an execution error. The screener never
    sees the labels.

    Security note: this runs model-generated code. With ``AIMPOINT_SCREEN_EXEC=subprocess``
    it is isolated (``python -I``, no inherited args) and CPU-limited, and the driver passes
    only data. The default ``inprocess`` path is fast but offers no isolation and is intended
    for trusted code (the baselines) and CI. Neither mode is a hardened sandbox; production
    use with an untrusted model should run inside the Inspect sandbox or a network-free
    container with a read-only filesystem. Tracked in the environment's known limits.
    """
    if EXEC_MODE != "subprocess":
        return _run_inprocess(source, queries, sigs, timeout)
    return _run_subprocess(source, queries, sigs, timeout)


def _run_inprocess(
    source: str, queries: list[str], sigs: Signatures, timeout: float
) -> list[bool | None]:
    n = len(queries)
    ns: dict = {}
    handler_set = False
    # Best-effort wall-clock guard. Only available on the main thread on POSIX; when the
    # scorer runs in a worker thread we simply proceed without it rather than failing.
    if hasattr(signal, "SIGALRM"):
        try:

            def _raise(_signum, _frame):
                raise _Timeout

            signal.signal(signal.SIGALRM, _raise)
            signal.setitimer(signal.ITIMER_REAL, timeout)
            handler_set = True
        except (ValueError, OSError):
            handler_set = False
    try:
        exec(source, ns)  # noqa: S102 - by contract this is a screener module
        screen = ns.get("screen")
        if not callable(screen):
            return [None] * n
        out: list[bool | None] = []
        sig_list, cleared_list = list(sigs.signatures), list(sigs.cleared)
        for q in queries:
            try:
                out.append(bool(screen(q, sig_list, cleared_list, THRESHOLD)))
            except Exception:
                out.append(None)
        return out
    except (_Timeout, Exception):
        return [None] * n
    finally:
        if handler_set:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)


def _run_subprocess(
    source: str, queries: list[str], sigs: Signatures, timeout: float
) -> list[bool | None]:
    n = len(queries)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src_file = tmp_path / "candidate_screener.py"
        src_file.write_text(source)
        data_file = tmp_path / "payload.json"
        data_file.write_text(
            json.dumps(
                {
                    "signatures": list(sigs.signatures),
                    "cleared": list(sigs.cleared),
                    "threshold": THRESHOLD,
                    "queries": queries,
                }
            )
        )
        driver_file = tmp_path / "driver.py"
        driver_file.write_text(_DRIVER)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(driver_file), str(src_file), str(data_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=_limit_cpu(int(timeout)),
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
        return [None if r is None else bool(r) for r in result]


def load_source_functions(source: str):
    """Import a screener source in-process (used only for trusted baseline code in tests)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "s.py"
        path.write_text(source)
        spec = importlib.util.spec_from_file_location("s", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # noqa: S102
        return mod
