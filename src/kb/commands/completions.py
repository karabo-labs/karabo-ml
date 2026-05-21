"""kb completions — Shell completion commands.

Generates shell completion scripts for bash, zsh, and fish.
Uses Click's built-in shell_completion module.
Uses lazy imports to avoid circular dependencies.
"""

from __future__ import annotations

import click
from rich.console import Console

console = Console()

SHELL_HELP = {
    "bash": "eval \"$(kb completions bash)\"",
    "zsh": "eval \"$(kb completions zsh)\"",
    "fish": "kb completions fish | source",
}


@click.group(name="completions")
def completions_group():
    """Generate shell completion scripts."""


def _get_source() -> str:
    """Generate completion source for the current shell (lazy import avoids circular)."""
    import click.shell_completion
    from kb.cli import cli

    ctx = click.Context(cli)
    comp = click.shell_completion.BashComplete(
        cli=cli,
        ctx_args={},
        prog_name="kb",
        complete_var="_KB_COMPLETE",
    )
    # Select based on click's auto-detection of shell
    return comp.source()


@completions_group.command(name="bash")
def bash():
    """Generate bash completions."""
    from click.shell_completion import BashComplete
    from kb.cli import cli

    comp = BashComplete(
        cli=cli,
        ctx_args={},
        prog_name="kb",
        complete_var="_KB_COMPLETE",
    )
    console.print(comp.source())


@completions_group.command(name="zsh")
def zsh():
    """Generate zsh completions."""
    from click.shell_completion import ZshComplete
    from kb.cli import cli

    comp = ZshComplete(
        cli=cli,
        ctx_args={},
        prog_name="kb",
        complete_var="_KB_COMPLETE",
    )
    console.print(comp.source())


@completions_group.command(name="fish")
def fish():
    """Generate fish completions."""
    from click.shell_completion import FishComplete
    from kb.cli import cli

    comp = FishComplete(
        cli=cli,
        ctx_args={},
        prog_name="kb",
        complete_var="_KB_COMPLETE",
    )
    console.print(comp.source())


@completions_group.command(name="install")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def install(shell: str):
    """Install completions (adds source line to shell rc)."""
    from pathlib import Path

    rc_files = {
        "bash": Path.home() / ".bashrc",
        "zsh": Path.home() / ".zshrc",
        "fish": Path.home() / ".config/fish/config.fish",
    }

    rc = rc_files.get(shell)
    if not rc:
        console.print(f"[red]Unknown shell: {shell}[/red]")
        return

    source_line = SHELL_HELP[shell]

    rc.parent.mkdir(parents=True, exist_ok=True)

    if rc.exists() and source_line in rc.read_text():
        console.print(f"[yellow]Completions already installed for {shell}.[/yellow]")
        return

    with open(rc, "a") as f:
        f.write(f"\n# kb CLI completions\n{source_line}\n")

    console.print(f"[green]Completions installed for {shell}![/green]")
    console.print(f"Run: [bold]source {rc}[/bold] or open a new terminal.")
