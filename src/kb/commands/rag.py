"""kb rag — RAG query commands."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from kb.client import RagClient
from kb.config import load_config
from kb.logger import get_logger

logger = get_logger()
console = Console()


def _get_client() -> RagClient:
    cfg = load_config()
    return RagClient(
        base_url=cfg["api"]["url"],
        timeout=cfg["api"]["timeout"],
    )


@click.group(name="rag")
def rag_group():
    """RAG query commands for DevOps documentation."""


@rag_group.command(name="query")
@click.argument("question", required=False, default=None)
@click.option("--top-k", default=5, help="Number of chunks to retrieve (1-20)")
@click.option("--no-sources", is_flag=True, help="Hide source citations")
@click.option("--json", "json_output", is_flag=True, help="Output raw JSON")
def query(question: str | None, top_k: int, no_sources: bool, json_output: bool):
    """Answer a DevOps question using RAG.

    If QUESTION is omitted, launches interactive prompt.
    """
    if not question:
        return _interactive(top_k=top_k, no_sources=no_sources)

    with _get_client() as client:
        health = client.health()
        if not health.get("reachable"):
            console.print(
                Panel(
                    "[red]RAG API is not reachable.[/red]\n"
                    f"Expected at: [bold]{client.base_url}[/bold]\n\n"
                    "Start it with: [bold]kb model serve[/bold]",
                    title="Connection Error",
                    border_style="red",
                )
            )
            sys.exit(1)

        result = client.query(question, top_k=top_k, include_sources=not no_sources)

    if json_output:
        import json as _json

        console.print(_json.dumps(result, indent=2))
        return

    if "error" in result and result.get("answer", "") == "":
        console.print(f"[red]Error:[/red] {result['error']}")
        return

    # Print answer
    md = Markdown(result.get("answer", "No answer returned."))
    console.print(Panel(md, title=f"Q: {question}", border_style="green"))

    # Print metadata
    meta = Table.grid(padding=(0, 2))
    meta.add_column(style="dim")
    meta.add_column()
    meta.add_row("Tokens", str(result.get("tokens_used", 0)))
    meta.add_row("Model", result.get("model", "unknown"))
    meta.add_row("Latency", f"{result.get('latency_ms', 0):.0f}ms")
    console.print(meta)

    # Print sources
    if not no_sources and result.get("sources"):
        src_table = Table(
            title="Sources",
            show_header=True,
            header_style="bold cyan",
            box=None,
        )
        src_table.add_column("#", style="dim")
        src_table.add_column("Source", style="cyan")
        src_table.add_column("Snippet")
        for i, src in enumerate(result["sources"], 1):
            src_table.add_row(
                str(i),
                f"{src.get('title', 'Unknown')}\n[dim]{src.get('url', '')}[/dim]",
                src.get("snippet", "")[:120] + "...",
            )
        console.print(src_table)


def _interactive(top_k: int, no_sources: bool):
    """Interactive RAG chat loop."""
    console.print(Panel("[bold]kb rag chat[/bold] — interactive mode. Type [/bold]/exit[/bold] to quit.", border_style="cyan"))

    with _get_client() as client:
        health = client.health()
        if not health.get("reachable"):
            console.print("[red]RAG API is not reachable. Start with: kb model serve[/red]")
            sys.exit(1)

        console.print("[dim]RAG API connected. Ask your DevOps questions![/dim]\n")

        while True:
            try:
                question = console.input("[bold cyan]kb> [/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Bye![/dim]")
                break

            if not question:
                continue
            if question.lower() in ("/exit", "/quit", "/q"):
                break
            if question.lower() == "/help":
                console.print(
                    "Commands:\n"
                    "  /exit, /quit, /q  — Exit chat\n"
                    "  /help             — Show this help\n"
                    "  /clear            — Clear screen"
                )
                continue
            if question.lower() == "/clear":
                console.clear()
                continue

            result = client.query(question, top_k=top_k, include_sources=not no_sources)

            if "error" in result and result.get("answer", "") == "":
                console.print(f"[red]Error:[/red] {result['error']}")
                continue

            md = Markdown(result.get("answer", ""))
            console.print(Panel(md, border_style="green"))

            meta_info = (
                f"[dim]{result.get('tokens_used', 0)} tokens"
                f" | {result.get('model', '?')}"
                f" | {result.get('latency_ms', 0):.0f}ms[/dim]"
            )
            console.print(meta_info)

            if not no_sources and result.get("sources"):
                for i, src in enumerate(result["sources"], 1):
                    console.print(
                        f"  [{i}] [cyan]{src.get('title', 'Unknown')}[/cyan] "
                        f"[dim]{src.get('url', '')}[/dim]"
                    )
            print()
