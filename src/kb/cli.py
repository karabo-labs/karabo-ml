"""kb — Karabo ML CLI.

Usage:
    kb rag query "how to setup ArgoCD"
    kb rag chat
    kb model serve
    kb drift check
    kb cluster status
    kb config init
    kb completions bash
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel

from kb import __version__
from kb.commands.cluster import cluster_group
from kb.commands.completions import completions_group
from kb.commands.config import config_group
from kb.commands.drift import drift_group
from kb.commands.model import model_group
from kb.commands.rag import rag_group
from kb.commands.tui import tui_group

console = Console()


class NaturalOrderGroup(click.Group):
    """Preserve command/group order as defined."""

    def list_commands(self, ctx):
        return list(self.commands)


@click.group(
    cls=NaturalOrderGroup,
    invoke_without_command=True,
)
@click.option("--version", "-V", is_flag=True, help="Show version and exit")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, version: bool, verbose: bool):
    """\u26a1 kb — Karabo ML: DevOps RAG Assistant CLI.

    Query your DevOps documentation with natural language.
    Powered by RAG (Retrieval-Augmented Generation) + Qdrant + OpenRouter.
    """
    if version:
        console.print(f"kb v{__version__}")
        sys.exit(0)

    # Set up logging
    from kb.logger import setup_logger

    level = "DEBUG" if verbose else "INFO"
    setup_logger(level=level)

    if ctx.invoked_subcommand is None:
        # No subcommand — show help
        console.print(
            Panel.fit(
                "[bold cyan]kb[/bold cyan] — Karabo ML\n"
                f"v{__version__} | DevOps RAG Assistant\n\n"
                "Commands:\n"
                "  [bold]rag query[/bold]       Answer a DevOps question\n"
                "  [bold]rag chat[/bold]        Interactive RAG chat\n"
                "  [bold]model serve[/bold]     Start RAG API server\n"
                "  [bold]model stop[/bold]      Stop RAG API server\n"
                "  [bold]drift check[/bold]     Check system health\n"
                "  [bold]drift collections[/bold]  List Qdrant collections\n"
                "  [bold]cluster status[/bold]  Check cluster status\n"
                "  [bold]cluster logs[/bold]    View service logs\n"
                "  [bold]config init[/bold]     Create config\n"
                "  [bold]config show[/bold]     Show config\n"
                "  [bold]completions install[/bold]  Install shell completions\n"
                "  [bold]tui[/bold]               Launch terminal dashboard\n\n"
                'Try: [bold]kb rag query "how to setup ArgoCD"[/bold]',
                border_style="cyan",
            )
        )


# Register all command groups
cli.add_command(rag_group)
cli.add_command(model_group)
cli.add_command(drift_group)
cli.add_command(cluster_group)
cli.add_command(config_group)
cli.add_command(completions_group)
cli.add_command(tui_group)

if __name__ == "__main__":
    cli()
