"""Build the frozen snapshot and answer key for pv_signal_triage from FAERS.

The design in one paragraph. FAERS is split at a cutoff. Reports from before it become the
snapshot the model reasons over; reports from after it become the answer key and are never
reachable from a tool. Candidate signals are drug/event pairs that clear the standard
disproportionality screen in the pre-cutoff window, which is what a pharmacovigilance
analyst's queue actually looks like on a Monday morning. The question the environment asks
is which of those still look like signals years later, and which were confounding by
indication, notoriety, or noise.

Why the bulk quarterly files rather than the openFDA API. Three reasons, in increasing
order of importance. The API's keyless quota is per-IP and shared, so a sixty-request build
is unreliable. The API's `count` endpoint returns at most 1000 terms and no grand total, so
the denominators for a reporting ratio have to be estimated from a truncated universe. And
the API's drug matching does not distinguish a suspect drug from one the patient merely
happened to be taking, which is the single largest source of spurious signal in
disproportionality analysis. The bulk files carry `role_cod`, so this build counts a
drug/event pair only when the drug was reported as primary or secondary suspect.

Reports are deduplicated by `caseid`, keeping the highest `primaryid`. FAERS ships every
revision of a case as a separate row, and counting all of them inflates exactly the cases
that got followed up, which are disproportionately the serious ones.

Usage:

    uv run python scripts/build_pv_snapshot.py            # download, parse, build
    uv run python scripts/build_pv_snapshot.py --report   # what is cached so far
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from datetime import date
from pathlib import Path

from aimpoint.core.determinism import SnapshotSpec, canonical_digest

ENV_DIR = (
    Path(__file__).resolve().parents[1] / "environments" / "biomedical_rd" / "pv_signal_triage"
)
ASSETS = ENV_DIR / "assets"
CACHE = ASSETS / ".cache"
SNAPSHOT_DIR = ASSETS / "snapshot"
ANSWERS_PATH = ASSETS / "answers.json"
MANIFEST_PATH = ASSETS / "manifest.json"

EXPORT_URL = "https://fis.fda.gov/content/Exports/faers_ascii_{quarter}.zip"

CUTOFF = date(2016, 1, 1)
PRE_QUARTERS = ["2015Q1", "2015Q2", "2015Q3", "2015Q4"]
POST_QUARTERS = ["2021Q1", "2021Q2", "2021Q3", "2021Q4"]

#: Active-ingredient tokens, matched against the `prod_ai` field. Chosen across therapeutic
#: classes before any outcome was inspected, mixing drugs with documented post-2016 label
#: changes against drugs with none, so the answer key is not concentrated in famous cases.
DRUGS = [
    "CANAGLIFLOZIN",
    "DAPAGLIFLOZIN",
    "EMPAGLIFLOZIN",
    "SITAGLIPTIN",
    "LIRAGLUTIDE",
    "METFORMIN",
    "INSULIN GLARGINE",
    "MONTELUKAST",
    "LEVOFLOXACIN",
    "CIPROFLOXACIN",
    "MOXIFLOXACIN",
    "AZITHROMYCIN",
    "AMOXICILLIN",
    "FEBUXOSTAT",
    "ALLOPURINOL",
    "ATORVASTATIN",
    "ROSUVASTATIN",
    "LISINOPRIL",
    "AMLODIPINE",
    "HYDROCHLOROTHIAZIDE",
    "WARFARIN",
    "APIXABAN",
    "RIVAROXABAN",
    "CLOPIDOGREL",
    "OMEPRAZOLE",
    "GABAPENTIN",
    "PREGABALIN",
    "DULOXETINE",
    "SERTRALINE",
    "ESCITALOPRAM",
    "BUPROPION",
    "QUETIAPINE",
    "ARIPIPRAZOLE",
    "OLANZAPINE",
    "CLOZAPINE",
    "LAMOTRIGINE",
    "LEVETIRACETAM",
    "LITHIUM",
    "METHOTREXATE",
    "ADALIMUMAB",
    "ETANERCEPT",
    "INFLIXIMAB",
    "RITUXIMAB",
    "PREDNISONE",
    "TRAMADOL",
    "OXYCODONE",
    "IBUPROFEN",
    "NAPROXEN",
    "ISOTRETINOIN",
    "FINASTERIDE",
]

#: Designated medical events: outcomes serious enough that one well-documented case warrants
#: review regardless of disproportionality. Adapted from the EMA Important Medical Event
#: concept. Used only for cost weighting, never for deciding whether a signal is real.
#: Escalating a spurious agranulocytosis signal consumes review and regulatory attention that
#: escalating a spurious nausea signal does not, and a metric that prices those alike is not
#: modelling the workload it claims to model.
DESIGNATED_MEDICAL_EVENTS = {
    "AGRANULOCYTOSIS",
    "APLASTIC ANAEMIA",
    "PANCYTOPENIA",
    "NEUTROPENIA",
    "THROMBOCYTOPENIA",
    "HAEMOLYTIC ANAEMIA",
    "ANAPHYLACTIC REACTION",
    "ANAPHYLACTIC SHOCK",
    "STEVENS-JOHNSON SYNDROME",
    "TOXIC EPIDERMAL NECROLYSIS",
    "DRUG REACTION WITH EOSINOPHILIA AND SYSTEMIC SYMPTOMS",
    "ANGIOEDEMA",
    "HEPATIC FAILURE",
    "HEPATITIS FULMINANT",
    "HEPATOTOXICITY",
    "HEPATIC NECROSIS",
    "LIVER INJURY",
    "RHABDOMYOLYSIS",
    "TORSADE DE POINTES",
    "VENTRICULAR FIBRILLATION",
    "CARDIAC ARREST",
    "SUDDEN DEATH",
    "MYOCARDIAL INFARCTION",
    "SEIZURE",
    "PROGRESSIVE MULTIFOCAL LEUKOENCEPHALOPATHY",
    "STATUS EPILEPTICUS",
    "INTERSTITIAL LUNG DISEASE",
    "PULMONARY FIBROSIS",
    "PANCREATITIS",
    "PANCREATITIS ACUTE",
    "RENAL FAILURE",
    "ACUTE KIDNEY INJURY",
    "DIABETIC KETOACIDOSIS",
    "FOURNIER'S GANGRENE",
    "LACTIC ACIDOSIS",
    "AORTIC ANEURYSM",
    "AORTIC DISSECTION",
    "TENDON RUPTURE",
    "AMPUTATION",
    "SUICIDAL IDEATION",
    "COMPLETED SUICIDE",
    "NEUROLEPTIC MALIGNANT SYNDROME",
    "SEROTONIN SYNDROME",
    "MYOPATHY",
    "OPTIC NEURITIS",
    "RETINAL DETACHMENT",
    "INTENTIONAL SELF-INJURY",
    "HEPATIC ENZYME INCREASED",
}

#: Only primary and secondary suspect drugs count. A concomitant medication is what the
#: patient also happened to be taking, and counting those is how confounding by indication
#: enters a disproportionality analysis dressed up as evidence.
SUSPECT_ROLES = {"PS", "SS"}

# The conventional screen (Evans 2001) is 3 cases, PRR >= 2, chi-square >= 4. Two deliberate
# departures.
#
# The case floors are raised well above 3, because at national reporting volumes 3 cases
# means nothing.
#
# More importantly, the queue is built at a LOWER ratio than the bar for calling a signal
# sustained, and the sustained bar is well above the conventional screen. Building both at
# PRR >= 2 was the first thing tried and it produced a degenerate task: pairs clearing the
# standard screen on twelve months of data almost all still clear it six years later, so the
# base rate came out at 0.66 and escalating the entire queue outscored triaging it. That is a
# true fact about spontaneous reporting and a useless benchmark.
#
# So the target is not "still disproportionate", which is common, but "became a strong and
# well-supported signal", which is not. That is also the decision the queue is actually for:
# an analyst is choosing which marginal pairs are worth committing review capacity to, and
# the ones worth it are the ones that turn into something a labelling committee would read.
# The known_limits say this plainly, because the label the key carries is not "is a real
# adverse drug reaction" and reading it that way would overstate what a score here means.
MIN_CASES_CANDIDATE = 10
MIN_PRR_CANDIDATE = 1.5
MIN_CHI2_CANDIDATE = 4.0
MIN_CASES_SUSTAINED = 40
MIN_PRR_SUSTAINED = 5.0
MIN_CHI2_SUSTAINED = 25.0

MIN_QUEUE = 6
MIN_DRUG_REPORTS = 300

#: Queues are capped at the most-reported pairs. Real signal queues are prioritised before a
#: human sees them, and an uncapped queue here reached 399 rows, which turns the task into an
#: exercise in reading a long table. The cap is applied before the answer key is split, so the
#: key never refers to a pair the model was not shown.
MAX_QUEUE = 60


def quarter_zip(quarter: str) -> Path:
    return CACHE / f"faers_{quarter}.zip"


def download(quarter: str) -> bool:
    """Fetch one quarterly export, skipping it if already cached and intact."""
    CACHE.mkdir(parents=True, exist_ok=True)
    target = quarter_zip(quarter)
    if target.exists() and _zip_ok(target):
        return True
    print(f"  downloading {quarter} ...", flush=True)
    subprocess.run(
        [
            "curl",
            "-sL",
            "--max-time",
            "900",
            "--retry",
            "3",
            "-C",
            "-",
            "-o",
            str(target),
            EXPORT_URL.format(quarter=quarter),
        ],
        check=False,
    )
    if not _zip_ok(target):
        print(f"  {quarter}: download incomplete", flush=True)
        target.unlink(missing_ok=True)
        return False
    print(f"  {quarter}: {target.stat().st_size / 1e6:.0f} MB", flush=True)
    return True


def _zip_ok(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1_000_000:
        return False
    result = subprocess.run(["unzip", "-t", str(path)], capture_output=True)
    return result.returncode == 0


def _member(quarter: str, table: str) -> str:
    """FAERS names members like ascii/DRUG15Q4.txt, using a two-digit year."""
    year, q = quarter[2:4], quarter[4:]
    return f"ascii/{table}{year}{q}.txt"


def _rows(quarter: str, table: str) -> list[str]:
    """Stream one table out of a cached zip without unpacking it to disk."""
    result = subprocess.run(
        ["unzip", "-p", str(quarter_zip(quarter)), _member(quarter, table)],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        # Some quarters capitalise members differently; retry case-insensitively.
        result = subprocess.run(
            ["unzip", "-p", "-C", str(quarter_zip(quarter)), _member(quarter, table)],
            capture_output=True,
        )
    return result.stdout.decode("utf-8", errors="replace").splitlines()


def latest_versions(quarters: list[str]) -> dict[str, str]:
    """Map each caseid to its highest primaryid across the period.

    FAERS ships every revision of a case as its own row. Counting all of them inflates the
    cases that received follow-up, which skews toward the serious ones and therefore toward
    exactly the signals the answer key is about.
    """
    keep: dict[str, str] = {}
    for quarter in quarters:
        for line in _rows(quarter, "REAC")[1:]:
            parts = line.split("$")
            if len(parts) < 3:
                continue
            primaryid, caseid = parts[0], parts[1]
            current = keep.get(caseid)
            if current is None or len(primaryid) > len(current) or primaryid > current:
                keep[caseid] = primaryid
    return keep


def tally(
    quarters: list[str],
) -> tuple[int, dict[str, int], dict[str, int], dict[tuple[str, str], int]]:
    """Count reports, drug exposures, event mentions, and drug/event co-occurrences."""
    keep = latest_versions(quarters)
    kept = set(keep.values())
    print(f"  {len(keep)} unique cases across {len(quarters)} quarters", flush=True)

    total = 0
    drug_reports: dict[str, int] = defaultdict(int)
    event_reports: dict[str, int] = defaultdict(int)
    pair_reports: dict[tuple[str, str], int] = defaultdict(int)
    counted: set[str] = set()

    for quarter in quarters:
        events_by_report: dict[str, set[str]] = defaultdict(set)
        for line in _rows(quarter, "REAC")[1:]:
            parts = line.split("$")
            if len(parts) < 3:
                continue
            primaryid, pt = parts[0], parts[2].strip().upper()
            if pt and primaryid in kept:
                events_by_report[primaryid].add(pt)

        drugs_by_report: dict[str, set[str]] = defaultdict(set)
        for line in _rows(quarter, "DRUG")[1:]:
            parts = line.split("$")
            if len(parts) < 6:
                continue
            primaryid, role, ingredient = parts[0], parts[3].strip().upper(), parts[5].upper()
            if role not in SUSPECT_ROLES or primaryid not in kept or not ingredient:
                continue
            for drug in DRUGS:
                if drug in ingredient:
                    drugs_by_report[primaryid].add(drug)

        for primaryid, events in events_by_report.items():
            if primaryid in counted:
                continue
            counted.add(primaryid)
            total += 1
            for event in events:
                event_reports[event] += 1
            for drug in drugs_by_report.get(primaryid, ()):
                drug_reports[drug] += 1
                for event in events:
                    pair_reports[(drug, event)] += 1
        print(f"  {quarter}: {total} reports counted so far", flush=True)

    return total, dict(drug_reports), dict(event_reports), dict(pair_reports)


def prr_and_chi2(a: int, n_drug: int, event_total: int, total: int) -> tuple[float, float]:
    """Proportional reporting ratio and its Yates-corrected chi-square, from the 2x2."""
    b = n_drug - a
    c = event_total - a
    d = total - n_drug - c
    if a <= 0 or b < 0 or c <= 0 or d <= 0:
        return 0.0, 0.0
    prr = (a / n_drug) / (c / (c + d))
    n = a + b + c + d
    denominator = (a + b) * (c + d) * (a + c) * (b + d)
    if denominator <= 0:
        return prr, 0.0
    chi2 = n * max(0.0, abs(a * d - b * c) - n / 2) ** 2 / denominator
    return prr, chi2


def build(pre, post) -> tuple[dict, dict]:
    """Turn the two period tallies into a pre-cutoff snapshot and a post-cutoff key."""
    total_pre, drug_pre, event_pre, pair_pre = pre
    total_post, drug_post, event_post, pair_post = post

    snapshot_drugs: dict[str, dict] = {}
    answers: dict[str, dict] = {}

    for drug in DRUGS:
        n_pre, n_post = drug_pre.get(drug, 0), drug_post.get(drug, 0)
        if n_pre < MIN_DRUG_REPORTS or n_post < MIN_DRUG_REPORTS:
            continue

        scored = []
        for (candidate_drug, event), a_pre in pair_pre.items():
            if candidate_drug != drug or a_pre < MIN_CASES_CANDIDATE:
                continue
            prr_pre, chi2_pre = prr_and_chi2(a_pre, n_pre, event_pre.get(event, 0), total_pre)
            if prr_pre < MIN_PRR_CANDIDATE or chi2_pre < MIN_CHI2_CANDIDATE:
                continue

            a_post = pair_post.get((drug, event), 0)
            prr_post, chi2_post = prr_and_chi2(a_post, n_post, event_post.get(event, 0), total_post)
            scored.append(
                (
                    {
                        "event": event,
                        "cases_pre": a_pre,
                        "prr_pre": round(prr_pre, 3),
                        "chi2_pre": round(chi2_pre, 1),
                        "designated_medical_event": event in DESIGNATED_MEDICAL_EVENTS,
                    },
                    a_post >= MIN_CASES_SUSTAINED
                    and prr_post >= MIN_PRR_SUSTAINED
                    and chi2_post >= MIN_CHI2_SUSTAINED,
                )
            )

        # Cap first, then split, so the key never names a pair the model was not shown.
        scored.sort(key=lambda row: (-row[0]["cases_pre"], row[0]["event"]))
        scored = scored[:MAX_QUEUE]

        candidates = [row[0] for row in scored]
        positives = [row[0]["event"] for row in scored if row[1]]
        negatives = [row[0]["event"] for row in scored if not row[1]]
        costs = {
            row[0]["event"]: (3.0 if row[0]["designated_medical_event"] else 1.0) for row in scored
        }

        if len(candidates) < MIN_QUEUE or not positives or not negatives:
            continue
        snapshot_drugs[drug] = {
            "drug": drug,
            "reports_pre": n_pre,
            "candidates": candidates,
        }
        answers[drug] = {
            "drug": drug,
            "positives": sorted(positives),
            "negatives": sorted(negatives),
            "negative_costs": {e: costs[e] for e in sorted(negatives)},
            "reports_post": n_post,
        }

    snapshot = {
        "cutoff": CUTOFF.isoformat(),
        "pre_quarters": PRE_QUARTERS,
        "total_reports_pre": total_pre,
        "drugs": snapshot_drugs,
    }
    answer_key = {
        "cutoff": CUTOFF.isoformat(),
        "post_quarters": POST_QUARTERS,
        "total_reports_post": total_post,
        "criteria": {
            "min_cases": MIN_CASES_SUSTAINED,
            "min_prr": MIN_PRR_SUSTAINED,
            "min_chi2": MIN_CHI2_SUSTAINED,
            "queue_min_cases": MIN_CASES_CANDIDATE,
            "queue_min_prr": MIN_PRR_CANDIDATE,
        },
        "by_drug": answers,
    }
    return snapshot, answer_key


def cached_tally(label: str, quarters: list[str]):
    """Tally a period, caching the result so thresholds can be retuned without reparsing.

    Parsing sixteen tables takes about nine minutes. The signal criteria are the part of this
    build most likely to need revision, and coupling a threshold change to a nine-minute
    reparse is how thresholds end up chosen by whoever had the patience rather than by what
    the data supports.
    """
    path = CACHE / f"tally_{label}.json"
    if path.exists():
        raw = json.loads(path.read_text())
        pairs = {tuple(k.split("||", 1)): v for k, v in raw["pairs"].items()}
        print(f"  reusing cached tally ({raw['total']} reports)", flush=True)
        return raw["total"], raw["drugs"], raw["events"], pairs

    total, drugs, events, pairs = tally(quarters)
    path.write_text(
        json.dumps(
            {
                "total": total,
                "drugs": drugs,
                "events": events,
                "pairs": {f"{d}||{e}": n for (d, e), n in pairs.items()},
            }
        )
    )
    return total, drugs, events, pairs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    quarters = PRE_QUARTERS + POST_QUARTERS
    if args.report:
        have = [q for q in quarters if quarter_zip(q).exists() and _zip_ok(quarter_zip(q))]
        print(f"{len(have)}/{len(quarters)} quarters cached: {', '.join(have)}")
        return

    print("Downloading FAERS quarterly exports")
    for quarter in quarters:
        if not download(quarter):
            raise SystemExit(f"could not fetch {quarter}; rerun to resume")

    print("\nTallying pre-cutoff period")
    pre = cached_tally("pre", PRE_QUARTERS)
    print("\nTallying post-cutoff period")
    post = cached_tally("post", POST_QUARTERS)

    snapshot, answer_key = build(pre, post)
    if not snapshot["drugs"]:
        raise SystemExit("no drug produced a usable queue")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (SNAPSHOT_DIR / "snapshot.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    ANSWERS_PATH.write_text(json.dumps(answer_key, indent=2, sort_keys=True))

    spec = SnapshotSpec(
        name="faers_pv_signals",
        version="1.0",
        cutoff=CUTOFF,
        digest=canonical_digest(SNAPSHOT_DIR),
        sources={"FAERS": f"pre {'+'.join(PRE_QUARTERS)}, post {'+'.join(POST_QUARTERS)}"},
    )
    MANIFEST_PATH.write_text(json.dumps(json.loads(spec.model_dump_json()), indent=2) + "\n")

    n_pos = sum(len(v["positives"]) for v in answer_key["by_drug"].values())
    n_neg = sum(len(v["negatives"]) for v in answer_key["by_drug"].values())
    print(f"\ndrugs: {len(snapshot['drugs'])}")
    print(f"candidates: {n_pos + n_neg} ({n_pos} sustained, {n_neg} decayed)")
    print(f"base rate: {n_pos / (n_pos + n_neg):.3f}")
    print(f"digest: {spec.digest}")


if __name__ == "__main__":
    main()
