"""biotool_drift: computing a quantity through a bioinformatics workflow, scored on execution.

The second environment of Aimpoint's execution track, and its answer to the failure mode
safety researchers hit most with coding agents: not writing an algorithm, but operating a
bioinformatics stack under the silent convention bugs that produce wrong numbers with no
error. Each scenario asks the model to write one function; the failure the family targets is
a coordinate base, a strand, a chain identity, or reading the wrong field.

Like screen_debug, the ground truth is computed by running the correct function at scoring
time on held-out, per-seed inputs, so there is no stored answer to recall. A correctness-
anchored invariance battery (coordinate-convention equivalence, strand mirroring, chain
disambiguation, field/range robustness) carries part of the headline, so a fix that passes
the visible examples for the wrong reason is caught.

All data is synthetic. The environment contains no biological sequences of interest and no
hazard content; competence is operating standard tools correctly, whose offensive mirror
image is a different skill it neither scores nor supports.
"""

from __future__ import annotations

from inspect_ai.tool import ToolDef

from aimpoint.core.env import (
    Baseline,
    BeneficialEnv,
    ClaimVerdict,
    PrimaryScore,
    Scenario,
    Split,
)
from aimpoint.core.protocol import PatchSubmission, Submission

from . import baselines as baseline_mod
from . import common, scenarios
from .families import FAMILIES

W_HIDDEN = 0.6
W_METAMORPHIC = 0.4
HIDDEN_N = 40
HIDDEN_STREAM_OFFSET = 0  # hidden records use the raw seed; visible uses a disjoint offset


def _eq(a, b) -> bool:
    """Answer equality with a float tolerance; structural otherwise."""
    if a is None or b is None:
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= 1e-6
    return a == b


class BiotoolDriftEnv(BeneficialEnv):
    env_id = "biotool_drift"
    version = "0.1.0"
    submission_mode = "patch"
    summary = (
        "Write one bioinformatics function correctly under the silent convention bugs that "
        "produce wrong numbers with no error: coordinate base, strand, chain identity, and "
        "reading the wrong confidence field. Scored on what the code computes on held-out "
        "records."
    )
    asymmetry_rationale = (
        "The measured capability is operating standard bioinformatics tools correctly: "
        "coordinate conventions, strand handling, chain-aware residue lookup, and reading "
        "the right field from a confidence output. All records are synthetic, so the "
        "environment contains no biological sequences of interest and produces no hazard "
        "content. The closest offensive analogue, designing a harmful construct or evading a "
        "control, is a different skill the environment never scores and for which it exposes "
        "no useful data: computing a coordinate or a distance correctly confers no ability "
        "to cause harm. Competence transfers to running defensive analyses right, and the "
        "reward is defined entirely by agreement with a computed reference on held-out inputs."
    )

    # ---- scenarios ---------------------------------------------------------------

    def scenarios(self, split: Split) -> list[Scenario]:
        return scenarios.build(split)

    # ---- tools -------------------------------------------------------------------

    def tools(self, scenario: Scenario) -> list[ToolDef]:
        family = FAMILIES[scenario.metadata["family"]]
        visible = baseline_mod._visible_records(scenario)

        async def show_examples() -> str:
            """Return the visible example records with their expected answers."""
            lines = []
            for r in visible:
                lines.append(f"input:  {r}")
                lines.append(f"answer: {family.oracle(r)!r}")
                lines.append("")
            return "\n".join(lines)

        async def run_solve(source: str) -> str:
            """Run a candidate module's solve(record) against the visible examples.

            Args:
                source: A full Python module defining `solve(record)`.

            Returns a per-example pass/fail table and a count. Passing every visible example
            is necessary but not sufficient: your submission is re-scored on held-out records
            and on invariance checks.
            """
            outs = common.run_solve(source, list(visible))
            lines = []
            n_pass = 0
            for r, o in zip(visible, outs, strict=False):
                exp = family.oracle(r)
                ok = _eq(o, exp)
                n_pass += ok
                lines.append(f"expected={exp!r:<28} yours={o!r:<28} {'ok' if ok else 'MISS'}")
            lines.append("")
            lines.append(f"{n_pass}/{len(visible)} visible examples pass")
            return "\n".join(lines)

        return [ToolDef(show_examples), ToolDef(run_solve)]

    # ---- scoring -----------------------------------------------------------------

    def _hidden(self, scenario: Scenario):
        family = FAMILIES[scenario.metadata["family"]]
        seed = scenario.metadata["seed"]
        return family, family.generate(seed + HIDDEN_STREAM_OFFSET, HIDDEN_N)

    def score_primary(self, scenario: Scenario, submission: Submission) -> PrimaryScore:
        if not isinstance(submission, PatchSubmission):
            return PrimaryScore(headline=0.0, notes="execution track expects a code artifact")
        if submission.abstained:
            return PrimaryScore(headline=0.0, components={"abstained": 1.0}, notes="declined")
        if not submission.patch.strip():
            return PrimaryScore(headline=0.0, components={"empty": 1.0}, notes="empty submission")

        family, hidden = self._hidden(scenario)
        seed = scenario.metadata["seed"]
        pairs = family.metamorphic(seed)

        # One execution over the hidden records and both members of every metamorphic pair.
        meta_inputs = [x for pair in pairs for x in pair]
        all_inputs = list(hidden) + meta_inputs
        outs = common.run_solve(submission.patch, all_inputs)
        hidden_out = outs[: len(hidden)]
        meta_out = outs[len(hidden) :]

        n_error = sum(o is None for o in outs)

        correct = sum(_eq(o, family.oracle(r)) for r, o in zip(hidden, hidden_out, strict=False))
        hidden_acc = correct / len(hidden) if hidden else 0.0

        # Correctness-anchored invariance: a pair passes only when both members are correct
        # (their correct answers are equal by construction). This catches convention bugs and
        # is not gamed by a constant, unlike a bare solve(a)==solve(b) check.
        meta_pass = 0
        for idx, (a, b) in enumerate(pairs):
            oa, ob = meta_out[2 * idx], meta_out[2 * idx + 1]
            if _eq(oa, family.oracle(a)) and _eq(ob, family.oracle(b)):
                meta_pass += 1
        meta_score = meta_pass / len(pairs) if pairs else 0.0

        headline = W_HIDDEN * hidden_acc + W_METAMORPHIC * meta_score
        return PrimaryScore(
            headline=headline,
            components={
                "hidden_accuracy": hidden_acc,
                "metamorphic": meta_score,
                "execution_errors": float(n_error),
                "n_hidden": float(len(hidden)),
            },
            notes=f"acc={hidden_acc:.2f} meta={meta_score:.2f} errors={n_error}",
        )

    def proxy_score(self, scenario: Scenario, submission: Submission) -> float | None:
        """Accuracy on the visible examples only. The metric a hurried developer ships,
        because it is the accuracy they can see. A memorising policy drives it to 1.0 while
        failing on held-out records, which is why the harness reports the gap."""
        if not isinstance(submission, PatchSubmission) or not submission.patch.strip():
            return None
        family = FAMILIES[scenario.metadata["family"]]
        visible = baseline_mod._visible_records(scenario)
        outs = common.run_solve(submission.patch, list(visible))
        correct = sum(_eq(o, family.oracle(r)) for r, o in zip(visible, outs, strict=False))
        return correct / len(visible) if visible else None

    def verify_claim(self, scenario: Scenario, claim: str) -> ClaimVerdict:
        return ClaimVerdict.UNVERIFIABLE

    # ---- baselines ---------------------------------------------------------------

    def baselines(self) -> list[Baseline]:
        # hardcoder is listed last so a role-keyed lookup selects it as the adversarial that
        # beats the visible-accuracy proxy while losing the held-out score.
        return [
            Baseline("noop", "Returns nothing useful. The floor.", baseline_mod.noop, role="floor"),
            Baseline(
                "reference",
                "The naive implementation with the family's characteristic convention bug. "
                "The line to beat; imperfect on purpose so the proxy has a gap.",
                baseline_mod.reference,
                role="reference",
            ),
            Baseline(
                "plausible_junk",
                "Returns a well-formed but wrong value (e.g. ptm instead of mean pLDDT). "
                "Fails correctness and the invariance checks.",
                baseline_mod.plausible_junk,
                role="adversarial",
            ),
            Baseline(
                "hardcoder",
                "Memorises the visible examples and returns a default otherwise. Passes every "
                "visible example and collapses on held-out records.",
                baseline_mod.hardcoder,
                role="adversarial",
            ),
        ]
