"""kb config — Configuration management commands."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from kb.config import load_config, init_config, CONFIG_FILE

console = Console()


@click.group(name="config")
def config_group():
    """Manage kb CLI configuration."""


@config_group.command(name="init")
@click.option("--force", is_flag=True, help="Overwrite existing config")
def init(force: bool):
    """Create default config file at ~/.kb/config.yaml."""
    path = init_config(force=force)
    console.print(f"[green]Config initialized:[/green] {path}")
    console.print("\nEdit it to set your API URLs and preferences.")


@config_group.command(name="show")
def show():
    """Show current configuration."""
    config = load_config()

    for section, values in config.items():
        table = Table(
            title=section.upper(),
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        if isinstance(values, dict):
            for key, val in values.items():
                table.add_row(key, str(val))
        else:
            table.add_row(section, str(values))

        console.print(table)
        console.print()

    console.print(f"[dim]Config file: {CONFIG_FILE}[/dim]")
    console.print("[dim]Env overrides: KB_API_URL, KB_QDRANT_URL, KB_LOG_LEVEL, KB_LOG_FILE, KB_PROJECT_DIR[/dim]")


@config_group.command(name="edit")
def edit():
    """Open config file in default editor."""
    import os
    import subprocess

    editor = os.environ.get("EDITOR", "nano")
    try:
        subprocess.run([editor, str(CONFIG_FILE)], check=True)
    except subprocess.CalledProcessError:
        console.print(f"[red]Editor failed. Edit manually:[/red] {CONFIG_FILE}")
        sys.exit(1)
