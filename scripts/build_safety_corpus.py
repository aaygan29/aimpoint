"""Recompute the digest manifest for the safety_judgment frozen data.

The corpus is hand-authored rather than fetched, so there is nothing to download. What this
script does is pin it: it digests `assets/frozen/` and writes the manifest the environment
verifies at load time.

That gate matters more for hand-authored data than for fetched data, not less. A snapshot
pulled from an API drifts when the upstream changes, which is at least an event someone
notices. An adjudication file in a repository drifts when somebody edits a case while
chasing a failing test, and nothing about that announces itself. Bumping the version here is
a deliberate act, so a changed answer key cannot be mistaken for a changed model.

Run after any edit to the taxonomy or the corpus:

    uv run python scripts/build_safety_corpus.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from aimpoint.core.determinism import SnapshotSpec, canonical_digest

ENV_DIR = Path(__file__).resolve().parents[1] / "environments" / "ai_safety" / "safety_judgment"
FROZEN_DIR = ENV_DIR / "assets" / "frozen"
MANIFEST_PATH = ENV_DIR / "assets" / "manifest.json"

NAME = "safety_judgment_corpus"
VERSION = "1.0"


def main() -> None:
    if not FROZEN_DIR.exists():
        raise SystemExit(f"no frozen data at {FROZEN_DIR}")

    corpus = json.loads((FROZEN_DIR / "corpus.json").read_text())
    taxonomy = json.loads((FROZEN_DIR / "taxonomy.json").read_text())

    spec = SnapshotSpec(
        name=NAME,
        version=VERSION,
        cutoff=date.fromisoformat(corpus["authored"]),
        digest=canonical_digest(FROZEN_DIR),
        sources={
            "corpus": f"hand-authored v{corpus['version']}, {len(corpus['cases'])} cases",
            "taxonomy": (
                f"hand-authored v{taxonomy['version']}, "
                f"{len(taxonomy['elements'])} elements, {len(taxonomy['rules'])} rules"
            ),
        },
    )

    MANIFEST_PATH.write_text(json.dumps(json.loads(spec.model_dump_json()), indent=2) + "\n")
    print(f"wrote {MANIFEST_PATH}")
    print(f"  digest {spec.digest}")
    print(f"  {len(corpus['cases'])} cases, {len(taxonomy['elements'])} elements")


if __name__ == "__main__":
    main()
