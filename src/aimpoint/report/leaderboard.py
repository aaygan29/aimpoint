"""Rendering committed run cards into a table.

The table carries the caveats next to the numbers rather than in a footnote. A leaderboard
row that shows 0.31 without showing that the reference policy scores 0.28 and that the
interval overlaps it is a row that will be quoted as though the model were good at
something. Columns here are chosen so that reading the number and reading its context are
the same act.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

COLUMNS = [
    "model",
    "env",
    "score",
    "vs floor",
    "vs reference",
    "proxy gap",
    "fabrication",
    "sycophancy",
    "n",
]


def load_cards(results_dir: Path) -> list[dict[str, Any]]:
    """Read every run card in a directory."""
    if not results_dir.exists():
        return []
    cards = []
    for path in sorted(results_dir.glob("*.json")):
        try:
            cards.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return cards


def _fmt(value: float | None, digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def render_markdown(results_dir: Path) -> str:
    """Render a markdown table, best score first."""
    cards = load_cards(results_dir)
    if not cards:
        return (
            "No run cards found.\n\n"
            "Produce one with:\n\n"
            "    uv run aimpoint run-env --env target_triage --model <provider/model>\n"
        )

    rows = []
    for card in cards:
        headline = card.get("headline")
        normalized = card.get("normalized") or {}
        probes = card.get("probes") or {}

        if headline is None:
            score = "suppressed"
            sort_key = -1.0
        else:
            score = f"{headline['mean']:.3f} [{headline['ci_lo']:.3f}, {headline['ci_hi']:.3f}]"
            sort_key = headline["mean"]

        rows.append(
            (
                sort_key,
                [
                    f"`{card.get('model', '?')}`",
                    card.get("env_id", "?"),
                    score,
                    _fmt(normalized.get("above_floor")),
                    _fmt(normalized.get("baseline_normalized"), 2),
                    _fmt(card.get("proxy_gap")),
                    _fmt(probes.get("fabrication_rate")),
                    _fmt(probes.get("sycophancy_index")),
                    str(card.get("replicates", "?")),
                ],
            )
        )

    rows.sort(key=lambda r: r[0], reverse=True)

    lines = [
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "|".join([" --- "] * len(COLUMNS)) + "|",
    ]
    lines += ["| " + " | ".join(cells) + " |" for _, cells in rows]

    reference = cards[0].get("reference_baseline")
    floor = (cards[0].get("baselines") or {}).get("noop")
    lines += [
        "",
        "**Reading this table.**",
        "",
        f"- `score` is the mean over replicates with a bootstrap 95% interval. "
        f"The no-op floor is {_fmt(floor)}.",
        f"- `vs reference` is normalised so 0.0 means the model matched doing nothing and "
        f"1.0 means it matched the `{reference}` reference policy. Below 1.0 means a policy "
        f"with no model in it did better.",
        "- `proxy gap` is the deliberately-flawed metric minus the real one. Large and "
        "positive is the signature of specification gaming.",
        "- `fabrication` is the share of checkable cited claims the frozen data contradicts.",
        "- `sycophancy` is the appropriate-update rate minus the capitulation rate. Near zero "
        "means the model moves as readily for bad reasons as good ones; negative means it "
        "resists correction.",
    ]
    return "\n".join(lines) + "\n"
