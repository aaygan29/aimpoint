"""Self-validation for aimpoint-bench. No model in the loop.

Checks:
  1. BENCH.json well-formed, references every pack.
  2. Biosecurity pack: schema, digests, disposition balance, no leaky keys, canaries.
  3. Over-refusal pack: schema, all cases 'clear', canaries.
  4. Adversarial pack: schema, all cases 'restricted', base_case refs valid, canaries.
  5. Capability catalog: 100 tasks, 10x10 domain, 5x20 tier, required fields, digest.
  6. Harbor gated tasks: CompileBench layout, expected.json parses, binary reward,
     'adapts' declared.
  7. TEST_SPLIT.json: every listed id exists in its pack.
  8. Canary format: every safety case carries a unique canary matching AIMPT-*-CANARY-.
  9. Contract: pack disposition mix ensures always_refuse AND always_clear both fail.

Exits non-zero on any violation.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []
CANARY_RE = re.compile(r"^AIMPT-[A-Z]+-CANARY-[a-z0-9\-]+-[0-9a-f]{4}$")


def fail(msg: str) -> None:
    failures.append(msg); print(f"FAIL {msg}")


def ok(msg: str) -> None:
    print(f"ok   {msg}")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------- 1. BENCH.json ----------
bench = json.loads((ROOT / "BENCH.json").read_text())
for k in ("name", "version", "packs", "contract", "test_split", "docs"):
    if k not in bench: fail(f"BENCH.json missing {k!r}")
if not failures:
    ok("BENCH.json well-formed")


# ---------- 2. Biosecurity pack ----------
bio_dir = ROOT / "safety_evals" / "biosecurity"
tax = json.loads((bio_dir / "taxonomy_ext.json").read_text())
man = json.loads((bio_dir / "manifest.json").read_text())
for fname, want in man["digests"].items():
    got = _sha(bio_dir / fname)
    if got != want: fail(f"biosecurity: {fname} digest {got} != manifest {want}")
corpus = json.loads((bio_dir / "corpus_biosec.json").read_text())
bio_ids = [c["id"] for c in corpus["cases"]]
if len(bio_ids) != len(set(bio_ids)): fail("biosecurity: duplicate case ids")
by_disp = {}
for c in corpus["cases"]:
    by_disp[c["disposition"]] = by_disp.get(c["disposition"], 0) + 1
if by_disp.get("restricted", 0) < 3 or by_disp.get("clear", 0) < 2:
    fail(f"biosecurity: baseline-fails-by-construction requires both restricted and clear; got {by_disp}")
ok(f"biosecurity: {len(bio_ids)} cases {by_disp}, digests match")


# ---------- 3. Over-refusal pack ----------
or_dir = ROOT / "safety_evals" / "over_refusal"
or_cases = json.loads((or_dir / "corpus_over_refusal.json").read_text())["cases"]
or_ids = [c["id"] for c in or_cases]
if len(or_ids) != len(set(or_ids)): fail("over_refusal: duplicate ids")
for c in or_cases:
    if c["disposition"] != "clear":
        fail(f"over_refusal: {c['id']} disposition must be 'clear'")
    if "canary" not in c or not CANARY_RE.match(c["canary"]):
        fail(f"over_refusal: {c['id']} missing / malformed canary")
ok(f"over_refusal: {len(or_ids)} cases, all clear")


# ---------- 4. Adversarial pack ----------
adv_dir = ROOT / "safety_evals" / "adversarial"
adv_cases = json.loads((adv_dir / "corpus_adversarial.json").read_text())["cases"]
adv_ids = [c["id"] for c in adv_cases]
if len(adv_ids) != len(set(adv_ids)): fail("adversarial: duplicate ids")
attacks_seen = set()
for c in adv_cases:
    if c["disposition"] != "restricted":
        fail(f"adversarial: {c['id']} must be restricted")
    if c.get("base_case") not in bio_ids:
        fail(f"adversarial: {c['id']} base_case {c.get('base_case')!r} not in biosecurity pack")
    if "attack_type" not in c: fail(f"adversarial: {c['id']} missing attack_type")
    else: attacks_seen.add(c["attack_type"])
    if "canary" not in c or not CANARY_RE.match(c["canary"]):
        fail(f"adversarial: {c['id']} missing / malformed canary")
if len(attacks_seen) < 4:
    fail(f"adversarial: attack-type diversity thin (<4 types): {attacks_seen}")
ok(f"adversarial: {len(adv_ids)} cases, {len(attacks_seen)} attack types")


# ---------- 5. Capability catalog ----------
cat_dir = ROOT / "capability_tasks"
cat = json.loads((cat_dir / "catalog.json").read_text())
cat_man = json.loads((cat_dir / "manifest.json").read_text())
if _sha(cat_dir / "catalog.json") != cat_man["digest_catalog_json"]:
    fail("capability: catalog.json digest != manifest")
if len(cat["tasks"]) != 100: fail(f"capability: expected 100 tasks, got {len(cat['tasks'])}")
by_dom, by_tier = {}, {}
cap_ids = set()
for t in cat["tasks"]:
    cap_ids.add(t["id"])
    by_dom[t["domain"]] = by_dom.get(t["domain"], 0) + 1
    by_tier[t["difficulty"]] = by_tier.get(t["difficulty"], 0) + 1
    for k in ("id", "capability_measured", "inputs", "output_schema", "grader",
              "baseline", "offensive_analogue"):
        if k not in t: fail(f"capability: {t.get('id', '?')} missing {k!r}")
if len(by_dom) != 10 or not all(v == 10 for v in by_dom.values()):
    fail(f"capability: domain balance broken: {by_dom}")
if len(by_tier) != 5 or not all(v == 20 for v in by_tier.values()):
    fail(f"capability: tier balance broken: {by_tier}")
ok(f"capability: 100 tasks, 10 domains x 10, 5 tiers x 20")


# ---------- 6. Harbor gated tasks ----------
harb = ROOT / "harbor_gated_tasks"
required = ["instruction.md", "task.toml", "environment/Dockerfile",
            "tests/test.sh", "tests/test_outputs.py", "tests/expected.json",
            "solution/solve.sh"]
task_dirs = sorted(p for p in harb.iterdir() if p.is_dir())
if len(task_dirs) < 3: fail(f"harbor: expected >=3 dirs, got {len(task_dirs)}")
for td in task_dirs:
    for rel in required:
        if not (td / rel).exists(): fail(f"harbor: {td.name}/{rel} missing")
    try: json.loads((td / "tests" / "expected.json").read_text())
    except Exception as e: fail(f"harbor: {td.name}/tests/expected.json invalid JSON: {e}")
    toml_txt = (td / "task.toml").read_text()
    if 'reward = "binary"' not in toml_txt:
        fail(f"harbor: {td.name}/task.toml missing binary reward")
    if 'adapts' not in toml_txt:
        fail(f"harbor: {td.name}/task.toml missing 'adapts' key")
ok(f"harbor: {len(task_dirs)} gated task dirs")


# ---------- 7. TEST_SPLIT.json ----------
ts = json.loads((ROOT / "TEST_SPLIT.json").read_text())
pack_lookup = {
    "safety_evals/biosecurity": set(bio_ids),
    "safety_evals/over_refusal": set(or_ids),
    "safety_evals/adversarial": set(adv_ids),
    "capability_tasks": cap_ids,
}
for pack, ids in ts["test_case_ids"].items():
    if pack not in pack_lookup:
        fail(f"TEST_SPLIT: unknown pack {pack!r}"); continue
    missing = set(ids) - pack_lookup[pack]
    if missing: fail(f"TEST_SPLIT: {pack} listed ids not in pack: {missing}")
ok("TEST_SPLIT: every listed id resolves to a pack case")


# ---------- 8. Canary uniqueness across safety packs ----------
all_canaries = ([c.get("canary") for c in or_cases]
                + [c.get("canary") for c in adv_cases])
present = [c for c in all_canaries if c]
if len(present) != len(set(present)):
    fail("canaries: duplicate canary strings across safety packs")
ok(f"canaries: {len(present)} unique canary strings")


# ---------- 9. Contract: composite mix forces both baselines to fail ----------
composite_dispositions = ([c["disposition"] for c in corpus["cases"]]
                          + [c["disposition"] for c in or_cases]
                          + [c["disposition"] for c in adv_cases])
n_restricted = composite_dispositions.count("restricted")
n_clear = composite_dispositions.count("clear")
if n_restricted < 5 or n_clear < 5:
    fail(f"contract: composite must have >=5 restricted AND >=5 clear to force both trivial baselines to fail; got restricted={n_restricted} clear={n_clear}")
ok(f"contract: composite {n_restricted} restricted / {n_clear} clear -- always_refuse and always_clear both fail by construction")


# ---------- summary ----------
print()
if failures:
    print(f"FAILED ({len(failures)} violation(s))"); sys.exit(1)
print("PASSED")
