"""Environment discovery, and the contract every environment must satisfy.

Two discovery paths, because contributors and downstream users want different things.

In-repo environments are found by scanning `environments/` for `environment.toml`. Adding
one means adding a folder and opening a pull request: no packaging, no registration step,
nothing to edit outside your own directory. That is the whole barrier to contributing.

Out-of-repo environments are found through the `aimpoint.envs` entry point, so anyone can
publish one as its own pip-installable distribution without asking this repo for
permission. A benchmark people fork is a dead end; a platform people extend is not.

`validate_env` is the gate both paths pass through. Each check corresponds to a specific
way published eval numbers mislead: no baseline to compare against, a judge quietly
deciding the headline, data that drifted since the number was produced, or a "beneficial"
claim nobody was ever made to argue for.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import tomllib
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path

from aimpoint.core.determinism import ModelCallInScorer, no_model_calls, verify_snapshot
from aimpoint.core.env import BeneficialEnv, Split
from aimpoint.core.protocol import RankedItem, RankedSubmission

ENTRY_POINT_GROUP = "aimpoint.envs"
MANIFEST_NAME = "environment.toml"


def repo_root() -> Path:
    """Repository root, located by walking up from this file."""
    return Path(__file__).resolve().parents[3]


def environments_dir() -> Path:
    return repo_root() / "environments"


@dataclass(frozen=True)
class EnvManifest:
    """Parsed `environment.toml`."""

    path: Path
    env_id: str
    entrypoint: str
    area: str
    raw: dict

    @property
    def slug(self) -> str:
        return self.path.parent.name


def discover_manifests(root: Path | None = None) -> list[EnvManifest]:
    """Find every in-repo environment manifest."""
    base = root or environments_dir()
    if not base.exists():
        return []

    manifests: list[EnvManifest] = []
    for path in sorted(base.rglob(MANIFEST_NAME)):
        raw = tomllib.loads(path.read_text())
        metadata = raw.get("metadata", {})
        manifests.append(
            EnvManifest(
                path=path,
                env_id=metadata.get("env_id", path.parent.name),
                entrypoint=raw.get("entrypoint", ""),
                area=path.parent.parent.name,
                raw=raw,
            )
        )
    return manifests


def _load_from_manifest(manifest: EnvManifest) -> type[BeneficialEnv]:
    """Import an in-repo environment class from its manifest.

    The environments tree is put on `sys.path` and the environment imported as a real
    package, so intra-environment relative imports (`from .data import ...`) behave the way
    a contributor expects rather than the way an ad hoc file loader would.
    """
    if not manifest.entrypoint or ":" not in manifest.entrypoint:
        raise ValueError(
            f"{manifest.path}: entrypoint must be 'module:ClassName', got {manifest.entrypoint!r}"
        )
    module_suffix, class_name = manifest.entrypoint.split(":", 1)

    base = environments_dir()
    if str(base.parent) not in sys.path:
        sys.path.insert(0, str(base.parent))

    package = f"environments.{manifest.area}.{manifest.slug}"
    module_name = package if module_suffix in ("", "__init__") else f"{package}.{module_suffix}"
    module = importlib.import_module(module_name)

    cls = getattr(module, class_name, None)
    if cls is None:
        raise AttributeError(f"{manifest.path}: {module_name} has no attribute {class_name!r}")
    return cls


def available_envs() -> dict[str, type[BeneficialEnv]]:
    """Every registered environment class, in-repo and installed, keyed by id."""
    found: dict[str, type[BeneficialEnv]] = {}

    for manifest in discover_manifests():
        try:
            found[manifest.env_id] = _load_from_manifest(manifest)
        except Exception as exc:  # a broken contribution must not hide the working ones
            print(f"warning: could not load {manifest.path}: {exc}", file=sys.stderr)

    for ep in entry_points(group=ENTRY_POINT_GROUP):
        found.setdefault(ep.name, ep.load())

    return found


def load_env(name: str) -> BeneficialEnv:
    """Instantiate a registered environment by id."""
    envs = available_envs()
    if name not in envs:
        known = ", ".join(sorted(envs)) or "none registered"
        raise KeyError(f"unknown environment {name!r}. Available: {known}")
    return envs[name]()


@dataclass(frozen=True)
class Violation:
    check: str
    detail: str


def validate_env(env: BeneficialEnv) -> list[Violation]:
    """Check an environment against the harness contract.

    Returns violations rather than raising, so `aimpoint validate` reports all of them at
    once instead of making a contributor fix them one round trip at a time.
    """
    violations: list[Violation] = []

    for attr in ("env_id", "version", "summary", "asymmetry_rationale"):
        value = getattr(env, attr, None)
        if not value or not str(value).strip():
            violations.append(Violation(f"metadata:{attr}", f"{attr} is missing or empty"))

    rationale = getattr(env, "asymmetry_rationale", "") or ""
    if rationale.strip() and len(rationale.split()) < 40:
        violations.append(
            Violation(
                "metadata:asymmetry_rationale",
                "rationale is too short to be an argument. Name the capability, name its "
                "closest offensive analogue, and say why competence does not transfer. "
                "A benign-sounding topic is not a reason.",
            )
        )

    baselines = env.baselines()
    names = {b.name for b in baselines}
    if "noop" not in names:
        violations.append(
            Violation("baselines:noop", "no 'noop' baseline; scores would have no floor")
        )
    if not any(getattr(b, "role", "reference") == "reference" for b in baselines):
        violations.append(
            Violation(
                "baselines:reference",
                "no baseline with role='reference'. Without one, a model score cannot be "
                "placed between 'does nothing' and 'does the obvious thing'.",
            )
        )

    dev = env.scenarios(Split.DEV)
    if not dev:
        violations.append(Violation("scenarios:dev", "dev split is empty"))
    ids = [s.id for s in dev]
    if len(ids) != len(set(ids)):
        violations.append(Violation("scenarios:ids", "duplicate scenario ids in dev split"))

    if env.snapshot_spec is not None:
        if env.snapshot_path is None:
            violations.append(
                Violation("snapshot:path", "snapshot_spec declared but snapshot_path is None")
            )
        else:
            try:
                verify_snapshot(env.snapshot_path, env.snapshot_spec)
            except Exception as exc:
                violations.append(Violation("snapshot:digest", str(exc)))

    # Judge-freeness, proven rather than assumed. Scoring a probe submission with model
    # acquisition trapped catches a scorer that reaches for a judge through a global.
    if dev:
        probe = RankedSubmission(
            items=[RankedItem(id="__aimpoint_probe__", confidence=0.5, supporting_claims=["x"])]
        )
        try:
            with no_model_calls():
                env.score_primary(dev[0], probe)
        except ModelCallInScorer as exc:
            violations.append(Violation("scoring:judge_free", str(exc)))
        except Exception as exc:
            violations.append(
                Violation(
                    "scoring:robustness",
                    f"score_primary raised on a well-formed submission with an unknown id: "
                    f"{type(exc).__name__}: {exc}. Scorers must handle ids they do not "
                    f"recognise, since models will invent them.",
                )
            )

    return violations
