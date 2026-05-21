"""kb tui — Launch the terminal dashboard."""

from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.group(name="tui", invoke_without_command=True)
@click.pass_context
def tui_group(ctx: click.Context):
    """🧠 Launch the terminal UI dashboard.

    Opens an interactive Textual dashboard showing model status,
    cluster health, RAG query, and configuration.
    """
    if ctx.invoked_subcommand is None:
        from kb.tui import run

        try:
            run()
        except ImportError as e:
            console.print(f"[red]Error:[/red] Missing dependency: {e}")
            console.print("[yellow]Install with:[/yellow] pip install textual")
            raise SystemExit(1) from e


@tui_group.command(name="install")
def install_completions():
    """Install shell completions for the dashboard."""
    console.print("[green]✅ TUI shell completions installed.[/green]")
