"""The `aimpoint` command line.

Four verbs, matching the four things anyone actually does with this repo: see what
environments exist, check that one satisfies the contract, run a model against one, and
render the results table.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from aimpoint import __version__
from aimpoint.core.env import Split
from aimpoint.core.registry import (
    available_envs,
    discover_manifests,
    load_env,
    validate_env,
)
from aimpoint.report.leaderboard import render_markdown
from aimpoint.runner import DEFAULT_REPLICATES, run, write_card


@click.group()
@click.version_option(__version__, prog_name="aimpoint")
def main() -> None:
    """Beneficial-capability environments for AI."""


@main.command("list")
def list_envs() -> None:
    """List every discoverable environment."""
    manifests = {m.env_id: m for m in discover_manifests()}
    envs = available_envs()
    if not envs:
        click.echo("No environments found.")
        return
    for env_id in sorted(envs):
        manifest = manifests.get(env_id)
        area = manifest.raw.get("metadata", {}).get("area", "?") if manifest else "installed"
        status = manifest.raw.get("metadata", {}).get("status", "?") if manifest else "-"
        click.echo(f"{env_id:<24} {area:<18} {status}")


@main.command()
@click.option("--env", "env_name", default=None, help="Environment id. Omit to check all.")
def validate(env_name: str | None) -> None:
    """Check environments against the harness contract.

    Exits non-zero on any violation, so CI can gate merges on it.
    """
    targets = [env_name] if env_name else sorted(available_envs())
    if not targets:
        click.echo("No environments found.")
        raise SystemExit(1)

    failed = False
    for name in targets:
        try:
            env = load_env(name)
        except Exception as exc:
            click.echo(f"{name}: FAILED TO LOAD: {exc}")
            failed = True
            continue

        violations = validate_env(env)
        if not violations:
            click.echo(f"{name}: ok")
            continue
        failed = True
        click.echo(f"{name}: {len(violations)} violation(s)")
        for violation in violations:
            click.echo(f"  [{violation.check}] {violation.detail}")

    raise SystemExit(1 if failed else 0)


@main.command()
@click.option("--env", "env_name", required=True, help="Environment id.")
@click.option("--model", required=True, help="Inspect model string, e.g. anthropic/claude-opus-5.")
@click.option("--split", default="dev", type=click.Choice(["dev", "test"]))
@click.option(
    "--replicates",
    default=DEFAULT_REPLICATES,
    show_default=True,
    help="Seeds to run. Below 3 the headline is suppressed, on purpose.",
)
@click.option("--seed", default=0, show_default=True)
@click.option("--limit", default=None, type=int, help="Cap scenarios, for smoke tests.")
@click.option("--max-turns", default=14, show_default=True)
@click.option("--out", default=None, type=click.Path(path_type=Path), help="Run card path.")
def run_env(
    env_name: str,
    model: str,
    split: str,
    replicates: int,
    seed: int,
    limit: int | None,
    max_turns: int,
    out: Path | None,
) -> None:
    """Run a model against an environment and write a run card."""
    env = load_env(env_name)

    violations = validate_env(env)
    if violations:
        click.echo(f"{env_name} fails validation; fix it before running:", err=True)
        for violation in violations:
            click.echo(f"  [{violation.check}] {violation.detail}", err=True)
        raise SystemExit(1)

    result = run(
        env,
        model=model,
        split=Split(split),
        replicates=replicates,
        seed=seed,
        max_turns=max_turns,
        limit=limit,
    )

    card = result.as_card()
    click.echo(json.dumps(card, indent=2, sort_keys=True))

    for warning in card.get("warnings", []):
        click.echo(f"warning: {warning}", err=True)

    path = out or Path("results") / f"{env_name}__{model.replace('/', '_')}.json"
    write_card(result, path)
    click.echo(f"\nrun card: {path}", err=True)


@main.command()
@click.option(
    "--results",
    default="results",
    type=click.Path(path_type=Path),
    help="Directory of run cards.",
)
@click.option(
    "--out", default=None, type=click.Path(path_type=Path), help="Write instead of print."
)
def leaderboard(results: Path, out: Path | None) -> None:
    """Render the results table from committed run cards."""
    table = render_markdown(results)
    if out:
        out.write_text(table)
        click.echo(f"wrote {out}", err=True)
    else:
        sys.stdout.write(table)


if __name__ == "__main__":
    main()
