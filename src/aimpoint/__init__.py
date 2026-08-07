"""Aimpoint: a harness for beneficial-capability environments.

An eval asks "can the model do X?" and produces a score. An RL environment asks the
same question and feeds that score back as training signal. Aimpoint builds the second
kind, which means the scoring rubric has to survive being optimized against.

Three properties are enforced by the harness rather than left to convention:

1. Headline scores are judge-free. A primary scorer receives a scenario, a typed
   submission, and frozen data. It is handed no model, so it cannot become an LLM judge
   by accident, and `aimpoint validate` additionally traps model calls at runtime.
2. Alignment probes are cross-cutting. Sycophancy, abstention, fabrication, and
   distribution shift live here, not in individual environments, so every contributed
   environment inherits them.
3. Baselines are mandatory. An environment that does not ship a no-op floor and a
   non-trivial reference policy fails validation, because a bare score is not a result.
"""

__version__ = "0.1.0"

from aimpoint.core.env import BeneficialEnv, Scenario, Split
from aimpoint.core.protocol import (
    Confidence,
    RankedItem,
    RankedSubmission,
    Submission,
)

__all__ = [
    "BeneficialEnv",
    "Confidence",
    "RankedItem",
    "RankedSubmission",
    "Scenario",
    "Split",
    "Submission",
    "__version__",
]
