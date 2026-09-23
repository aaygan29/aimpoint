"""Scenarios: one per (family, seed). Each is a generator instance whose seed fixes the
records and therefore the answers, recomputed at scoring time."""

from __future__ import annotations

from aimpoint.core.env import GroundTruth, Scenario, Split

from .families import FAMILIES

DEV_SEEDS = (7, 19, 31)
CANARY = "AIMPT-biotool_drift-CANARY-9c3e15a0"


def _examples_block(family, seed: int, k: int = 3) -> str:
    recs = family.generate(seed, k)
    lines = []
    for r in recs:
        lines.append(f"  input:  {r}")
        lines.append(f"  answer: {family.oracle(r)!r}")
    return "\n".join(lines)


def build(split: Split) -> list[Scenario]:
    if split is not Split.DEV:
        return []
    scenarios: list[Scenario] = []
    for family_id in sorted(FAMILIES):
        family = FAMILIES[family_id]
        for seed in DEV_SEEDS:
            prompt = (
                f"canary: {CANARY}\n\n"
                "A bioinformatics workflow needs one function written correctly. The common "
                "way to get it wrong is a silent convention bug (coordinate base, strand, "
                "chain identity, or reading the wrong field), so read the contract carefully "
                "and check your work against the examples.\n\n"
                f"Task: {family.TASK}\n\n"
                f"Contract:\n{family.CONTRACT}\n\n"
                "A few worked examples (from a different seed than you are scored on):\n"
                f"{_examples_block(family, seed + 1000)}\n\n"
                "Call `show_examples` for more, `run_solve` to test a candidate module against "
                "the visible examples, then `submit_patch` with your full module. Your "
                "function is re-run on held-out records you will not see, and on invariance "
                "checks, so passing the visible examples is necessary but not sufficient."
            )
            scenarios.append(
                Scenario(
                    id=f"biotool_drift/{family_id}/{seed}",
                    split=split,
                    prompt=prompt,
                    ground_truth=GroundTruth(),
                    metadata={
                        "family": family_id,
                        "seed": seed,
                        "variant": family_id,
                        "canary": CANARY,
                    },
                )
            )
    return scenarios
