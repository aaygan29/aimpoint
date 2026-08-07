"""Seeds, frozen clocks, and the snapshot gate.

Reproducibility here is a hard requirement rather than an aspiration, because the same
artifact is meant to serve as both an eval and an RL environment. A reward function that
drifts is worse than no reward function: it silently rewards different behaviour at
different times, and the resulting policy is not attributable to anything.

Three sources of drift are closed off:

- Wall-clock time. Environments read `frozen_now()`, never `datetime.now()`. A
  retrospective-holdout task whose notion of "now" advances is a task whose answer key
  changes underneath it.
- Live network data. Eval-time code never calls an API. Data is a checksum-pinned
  snapshot, and a mismatch is a hard failure rather than a warning. This is not
  hypothetical: the Open Targets endpoint rate-limited during development of this repo,
  and rate limits are the benign version. Silent upstream revision is the real hazard.
- Unseeded sampling. Per-sample seeds are derived by hash from the run seed, so
  replicates are independent, reproducible, and unaffected by execution order or
  parallelism.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SnapshotMismatch(RuntimeError):
    """Raised when on-disk data does not match its manifest.

    Deliberately fatal. A run against unverified data produces numbers that cannot be
    compared to any other run, and a number that cannot be compared is worse than a
    missing number because it still looks like evidence.
    """


class SnapshotSpec(BaseModel):
    """Identity of a frozen data snapshot."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    cutoff: date = Field(
        description="Knowledge cutoff. Nothing dated after this may appear in the snapshot; "
        "everything after it is answer key."
    )
    digest: str = Field(description="Canonical digest over snapshot contents.")
    sources: dict[str, str] = Field(
        default_factory=dict,
        description="Upstream source name to accessed-version string, for provenance.",
    )


def canonical_digest(path: Path) -> str:
    """Digest a snapshot directory in a way that is stable across machines.

    Files are visited in sorted relative-path order and both the path and the bytes are
    folded in, so a rename is as detectable as an edit. Hidden files are skipped so that
    editor and filesystem debris cannot invalidate an otherwise-clean snapshot.
    """
    hasher = hashlib.blake2b(digest_size=32)
    root = Path(path)
    files = sorted(
        (p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for file in files:
        hasher.update(file.relative_to(root).as_posix().encode())
        hasher.update(b"\0")
        hasher.update(file.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def verify_snapshot(path: Path, spec: SnapshotSpec) -> None:
    """Fail loudly if the snapshot on disk is not the one the spec describes."""
    if not path.exists():
        raise SnapshotMismatch(
            f"snapshot {spec.name!r} v{spec.version} not found at {path}. "
            f"Rebuild it with: uv run python scripts/build_snapshot.py"
        )
    actual = canonical_digest(path)
    if actual != spec.digest:
        raise SnapshotMismatch(
            f"snapshot {spec.name!r} v{spec.version} digest mismatch at {path}.\n"
            f"  expected: {spec.digest}\n"
            f"  actual:   {actual}\n"
            "Data changed since the manifest was written. Scores computed against it are "
            "not comparable to published results. Restore the snapshot or bump its version."
        )


def frozen_now(spec: SnapshotSpec) -> datetime:
    """The only legitimate notion of 'now' inside an environment.

    Pinned to the snapshot cutoff so that a scenario means the same thing whenever it is
    run. Environments that need a date must call this.
    """
    return datetime.combine(spec.cutoff, datetime.min.time(), tzinfo=UTC)


def derive_seed(run_seed: int, *parts: str | int) -> int:
    """Derive a stable child seed from a run seed and identifying parts.

    Hash-based rather than counter-based so that seeds do not depend on how work was
    scheduled. Sample 7 gets the same seed whether it ran first, last, or on another
    machine, which is what lets replicate variance mean what it claims to mean.
    """
    payload = json.dumps([run_seed, *[str(p) for p in parts]], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big") % (2**31 - 1)


class ModelCallInScorer(RuntimeError):
    """Raised when a primary scorer tries to call a model.

    Primary scorers are handed no model handle, so this can only fire if a scorer reached
    for one through a global. That is exactly the leak worth trapping: it is easy to do
    accidentally and it silently converts a deterministic headline metric into a noisy
    judged one.
    """


class no_model_calls:
    """Context manager that makes any model acquisition raise.

    Used by `aimpoint validate` to prove judge-freeness empirically rather than trusting
    that the type signature was respected.
    """

    def __init__(self) -> None:
        self._saved: object = None

    def __enter__(self) -> no_model_calls:
        import inspect_ai.model as model_module

        self._saved = model_module.get_model

        def _trap(*args: object, **kwargs: object) -> object:
            raise ModelCallInScorer(
                "a primary scorer attempted to acquire a model. Primary scores must be a "
                "pure function of (scenario, submission, snapshot). Move judged reasoning "
                "into score_secondary(), where it is reported but never part of the headline."
            )

        model_module.get_model = _trap  # type: ignore[assignment]
        return self

    def __exit__(self, *exc: object) -> None:
        import inspect_ai.model as model_module

        model_module.get_model = self._saved  # type: ignore[assignment]
