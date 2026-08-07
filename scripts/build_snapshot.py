"""Build the frozen snapshot for the target_triage environment.

The task is a retrospective holdout: the model sees the therapeutic landscape as it stood
at a cutoff date and predicts which target mechanisms will earn a first approval for a
given disease afterwards. That only works if the split is real, so the leakage controls
below are the substance of this script rather than housekeeping.

What makes the split trustworthy is ChEMBL's `first_approval` year, which is a recorded
fact about the world rather than an inference. Three exclusions follow from it:

1. Any molecule approved on or after the cutoff is removed from the snapshot entirely,
   along with its mechanism and indication rows. Leaving a post-cutoff drug visible would
   hand over the answer.
2. A target only counts as a positive if it had no approved drug for *that indication*
   before the cutoff. Naming a mechanism that was already approved for the disease is not
   a prediction.
3. Negatives are mechanisms that actually entered trials for the disease before the cutoff
   and never reached approval. They are distinguishable from "never tried", which is why
   the scorer can give credit for avoiding known dead ends.

Known limits, stated because they bound what results from this snapshot can claim:

- ChEMBL's indication annotations reflect the current release. A pre-cutoff trial recorded
  retrospectively will appear in the snapshot even though a contemporary observer might not
  have connected it to the disease. This inflates how complete the pre-cutoff view looks.
- Approval year is not discovery year. A target whose biology was obvious in 2010 and whose
  drug was approved in 2019 counts as a post-cutoff positive, so the task rewards knowing
  the development pipeline as much as knowing the biology.
- Absence of an approval is not evidence of a bad target. Many mechanisms fail for
  commercial or trial-design reasons, so `negatives` means "did not reach approval", not
  "was biologically wrong".

Run: uv run python scripts/build_snapshot.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
PAGE = 1000

#: Everything dated before this is context; everything on or after it is answer key.
DEFAULT_CUTOFF_YEAR = 2015

#: Diseases chosen for having substantial pre-cutoff trial activity and a non-trivial
#: number of post-cutoff first approvals, so that both the positive and negative classes
#: are populated. The last entry is deliberately quiet: it anchors the abstention
#: scenarios, where the correct answer is that the evidence does not support a shortlist.
DISEASES: list[dict[str, str]] = [
    {"efo_id": "MONDO:0005148", "name": "type 2 diabetes mellitus"},
    {"efo_id": "EFO:0001073", "name": "obesity"},
    {"efo_id": "MONDO:0005277", "name": "migraine disorder"},
    {"efo_id": "EFO:0000274", "name": "atopic eczema"},
    {"efo_id": "EFO:0000676", "name": "psoriasis"},
    {"efo_id": "MONDO:0005301", "name": "multiple sclerosis"},
]


def _get(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET with retries. ChEMBL throttles, and a half-built snapshot is worse than a slow one."""
    for attempt in range(5):
        try:
            response = client.get(f"{CHEMBL}/{path}", params=params)
            if response.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            if attempt == 4:
                raise RuntimeError(f"giving up on {path} after 5 attempts: {exc}") from exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def _paged(client: httpx.Client, path: str, key: str, params: dict[str, Any]) -> list[dict]:
    """Walk every page of a ChEMBL collection endpoint."""
    out: list[dict] = []
    offset = 0
    while True:
        payload = _get(client, path, {**params, "limit": PAGE, "offset": offset})
        rows = payload.get(key, [])
        out.extend(rows)
        total = payload.get("page_meta", {}).get("total_count", 0)
        offset += PAGE
        if offset >= total or not rows:
            return out


def _phase(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fetch_catalog(client: httpx.Client) -> dict[str, dict]:
    """Pull the human protein target catalog: the candidate universe.

    Deliberately defined by a criterion with nothing to do with drugs or approvals, namely
    "is a human protein target in ChEMBL". That makes the catalog leakage-free by
    construction rather than by analysis.

    The first version of this snapshot derived the catalog from the drugs of the six study
    diseases instead, and it was quietly broken in both directions. 37% of positives were
    unreachable, because a target whose only drugs were post-cutoff got filtered out along
    with them, so the model was scored on naming things it had never been shown. Repairing
    that by adding just the missing targets would have been worse: every one of them would
    have had zero pre-cutoff drugs while no negative did, turning "no drug yet" into a
    perfect tell. Widening the frame fixes both, because thousands of catalog entries have
    no drug for any given disease and the positives no longer stand out.
    """
    catalog: dict[str, dict] = {}
    for target_type in ("SINGLE PROTEIN", "PROTEIN COMPLEX"):
        print(f"  catalog: {target_type}", file=sys.stderr)
        for row in _paged(
            client,
            "target.json",
            "targets",
            {"target_type": target_type, "organism": "Homo sapiens"},
        ):
            tid = row.get("target_chembl_id")
            if not tid:
                continue
            catalog[tid] = {
                "target_chembl_id": tid,
                "name": row.get("pref_name"),
                "target_type": row.get("target_type"),
                "accessions": sorted(
                    {
                        c.get("accession")
                        for c in row.get("target_components", [])
                        if c.get("accession")
                    }
                ),
            }
    return catalog


def fetch(client: httpx.Client, cutoff_year: int) -> dict[str, Any]:
    """Pull indications, molecules, mechanisms, and targets for the disease set."""
    indications: dict[str, list[dict]] = {}
    molecule_ids: set[str] = set()

    for disease in DISEASES:
        print(f"  indications: {disease['name']}", file=sys.stderr)
        rows = _paged(
            client, "drug_indication.json", "drug_indications", {"efo_id": disease["efo_id"]}
        )
        indications[disease["efo_id"]] = rows
        molecule_ids.update(r["molecule_chembl_id"] for r in rows if r.get("molecule_chembl_id"))

    print(f"  molecules: {len(molecule_ids)}", file=sys.stderr)
    molecules: dict[str, dict] = {}
    ids = sorted(molecule_ids)
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        for row in _paged(
            client, "molecule.json", "molecules", {"molecule_chembl_id__in": ",".join(chunk)}
        ):
            molecules[row["molecule_chembl_id"]] = row

    print("  mechanisms", file=sys.stderr)
    mechanisms: list[dict] = []
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        mechanisms.extend(
            _paged(
                client, "mechanism.json", "mechanisms", {"molecule_chembl_id__in": ",".join(chunk)}
            )
        )

    target_ids = sorted({m["target_chembl_id"] for m in mechanisms if m.get("target_chembl_id")})
    print(f"  targets: {len(target_ids)}", file=sys.stderr)
    targets: dict[str, dict] = {}
    for start in range(0, len(target_ids), 50):
        chunk = target_ids[start : start + 50]
        for row in _paged(
            client, "target.json", "targets", {"target_chembl_id__in": ",".join(chunk)}
        ):
            targets[row["target_chembl_id"]] = row

    catalog = fetch_catalog(client)
    print(f"  catalog size: {len(catalog)}", file=sys.stderr)

    return {
        "indications": indications,
        "molecules": molecules,
        "mechanisms": mechanisms,
        "targets": targets,
        "catalog": catalog,
    }


def split(raw: dict[str, Any], cutoff_year: int) -> tuple[dict, dict]:
    """Partition into a pre-cutoff snapshot and a post-cutoff answer key."""
    molecules: dict[str, dict] = raw["molecules"]
    mechanisms: list[dict] = raw["mechanisms"]
    targets: dict[str, dict] = raw["targets"]

    def approval_year(mol_id: str) -> int | None:
        row = molecules.get(mol_id) or {}
        year = row.get("first_approval")
        return int(year) if year else None

    # Exclusion 1: molecules approved on or after the cutoff never appear in the snapshot.
    post_cutoff_molecules = {mid for mid in molecules if (approval_year(mid) or 0) >= cutoff_year}

    mech_by_molecule: dict[str, list[dict]] = defaultdict(list)
    for mech in mechanisms:
        mech_by_molecule[mech["molecule_chembl_id"]].append(mech)

    snapshot_targets: dict[str, dict] = {}
    snapshot_mechanisms: list[dict] = []
    snapshot_drugs: list[dict] = []
    ground_truth: dict[str, dict] = {}

    for disease in DISEASES:
        efo = disease["efo_id"]
        rows = raw["indications"][efo]

        approved_pre: set[str] = set()  # targets already approved for THIS disease
        approved_post: set[str] = set()  # targets first approved for it after the cutoff
        trialled_pre: set[str] = set()  # targets that entered trials for it before the cutoff
        ever_approved: set[str] = set()

        for row in rows:
            mol_id = row.get("molecule_chembl_id")
            if not mol_id:
                continue
            phase = _phase(row.get("max_phase_for_ind"))
            year = approval_year(mol_id)
            mech_targets = {
                m["target_chembl_id"]
                for m in mech_by_molecule.get(mol_id, [])
                if m.get("target_chembl_id")
            }
            if not mech_targets:
                continue

            if phase >= 4.0 and year is not None:
                ever_approved |= mech_targets
                (approved_post if year >= cutoff_year else approved_pre).update(mech_targets)
            if phase >= 2.0 and (year is None or year < cutoff_year):
                trialled_pre |= mech_targets

            # Snapshot rows: pre-cutoff molecules only.
            if mol_id not in post_cutoff_molecules:
                mol = molecules[mol_id]
                snapshot_drugs.append(
                    {
                        "disease": efo,
                        "molecule_chembl_id": mol_id,
                        "name": mol.get("pref_name"),
                        "molecule_type": mol.get("molecule_type"),
                        "first_approval": year,
                        "max_phase_for_indication": phase,
                        "withdrawn": bool(mol.get("withdrawn_flag")),
                    }
                )

        # Exclusion 2: a target already approved for this disease is not a prediction.
        positives = approved_post - approved_pre
        # Exclusion 3: negatives were genuinely tried and did not arrive.
        negatives = trialled_pre - ever_approved

        ground_truth[efo] = {
            "disease_name": disease["name"],
            "positives": sorted(positives),
            "negatives": sorted(negatives),
            "already_approved_pre_cutoff": sorted(approved_pre),
        }

    for mech in mechanisms:
        if mech["molecule_chembl_id"] in post_cutoff_molecules:
            continue
        tid = mech.get("target_chembl_id")
        if not tid:
            continue
        snapshot_mechanisms.append(
            {
                "molecule_chembl_id": mech["molecule_chembl_id"],
                "target_chembl_id": tid,
                "mechanism_of_action": mech.get("mechanism_of_action"),
                "action_type": mech.get("action_type"),
            }
        )
    # The visible target universe is the full human catalog, not the subset reachable from
    # these diseases' drugs. Entries seen in the disease data are enriched with the fuller
    # record where one exists.
    snapshot_targets = dict(raw["catalog"])
    for tid, row in targets.items():
        snapshot_targets[tid] = {
            "target_chembl_id": tid,
            "name": row.get("pref_name"),
            "target_type": row.get("target_type"),
            "accessions": sorted(
                {c.get("accession") for c in row.get("target_components", []) if c.get("accession")}
            ),
        }

    snapshot = {
        "cutoff_year": cutoff_year,
        "diseases": DISEASES,
        "targets": snapshot_targets,
        "mechanisms": snapshot_mechanisms,
        "drugs": snapshot_drugs,
    }
    answers = {"cutoff_year": cutoff_year, "by_disease": ground_truth}
    return snapshot, answers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=int, default=DEFAULT_CUTOFF_YEAR)
    parser.add_argument("--out", type=Path, default=Path("data/snapshots/target_triage_v0"))
    args = parser.parse_args()

    print(f"Building target_triage snapshot, cutoff {args.cutoff}", file=sys.stderr)
    with httpx.Client(timeout=120, headers={"Accept": "application/json"}) as client:
        raw = fetch(client, args.cutoff)

    snapshot, answers = split(raw, args.cutoff)

    # The snapshot directory holds exactly what the model may see, and nothing else. The
    # answer key is a sibling file outside it, so it is neither reachable through the
    # environment's tools nor folded into the digest. That separation is what lets a
    # held-out split ship its snapshot publicly while withholding its answers.
    args.out.mkdir(parents=True, exist_ok=True)
    snapshot_path = args.out / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=1, sort_keys=True) + "\n")
    print(
        f"  wrote {snapshot_path} ({snapshot_path.stat().st_size / 1024:.0f} KB)", file=sys.stderr
    )

    answers_path = args.out.parent / f"{args.out.name}.answers.json"
    answers_path.write_text(json.dumps(answers, indent=1, sort_keys=True) + "\n")
    print(f"  wrote {answers_path} ({answers_path.stat().st_size / 1024:.0f} KB)", file=sys.stderr)

    # The manifest is written by a separate step so the digest covers exactly what shipped.
    from aimpoint.core.determinism import canonical_digest

    digest = canonical_digest(args.out)
    manifest = {
        "name": "target_triage",
        "version": "0",
        "cutoff": f"{args.cutoff}-01-01",
        "digest": digest,
        "sources": {
            "chembl": "https://www.ebi.ac.uk/chembl/api/data (release current at build time)"
        },
    }
    manifest_path = args.out.parent / "target_triage_v0.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"  wrote {manifest_path}\n  digest {digest}", file=sys.stderr)

    for entry in answers["by_disease"].values():
        print(
            f"  {entry['disease_name']:<28} "
            f"positives={len(entry['positives']):<3} negatives={len(entry['negatives']):<4} "
            f"already-approved={len(entry['already_approved_pre_cutoff'])}",
            file=sys.stderr,
        )

    problems = audit(snapshot, answers)
    if problems:
        print("\nSNAPSHOT AUDIT FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("\n  audit passed", file=sys.stderr)
    return 0


def audit(snapshot: dict, answers: dict) -> list[str]:
    """Check the split for the two ways it silently breaks.

    Run on every build because both failures look like ordinary data from the outside. An
    unreachable positive caps the achievable score below 1.0 and reads as model
    incompetence. A separating artifact does the opposite and reads as model insight. Both
    survived the first build of this snapshot, which is the reason this function exists.
    """
    problems: list[str] = []
    catalog = set(snapshot["targets"])

    # Every answer must be nameable from what the model can see.
    for entry in answers["by_disease"].values():
        unreachable = [t for t in entry["positives"] if t not in catalog]
        if unreachable:
            problems.append(
                f"{entry['disease_name']}: {len(unreachable)} positive(s) absent from the "
                f"target catalog, so they cannot be named: {unreachable}"
            )

    # "Has no pre-cutoff drug for this disease" must not separate positives from the field.
    drugged_by_disease: dict[str, set[str]] = defaultdict(set)
    mech_targets = {m["molecule_chembl_id"]: m["target_chembl_id"] for m in snapshot["mechanisms"]}
    for drug in snapshot["drugs"]:
        tid = mech_targets.get(drug["molecule_chembl_id"])
        if tid:
            drugged_by_disease[drug["disease"]].add(tid)

    for efo, entry in answers["by_disease"].items():
        drugged = drugged_by_disease[efo]
        undrugged_catalog = len(catalog - drugged)
        undrugged_positives = sum(1 for t in entry["positives"] if t not in drugged)
        if undrugged_positives and undrugged_catalog < 50 * undrugged_positives:
            problems.append(
                f"{entry['disease_name']}: only {undrugged_catalog} catalog targets lack a "
                f"pre-cutoff drug while {undrugged_positives} positive(s) do; 'no drug yet' "
                f"is close to a tell. Widen the candidate universe."
            )
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
