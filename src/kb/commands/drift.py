"""kb drift — Health and drift checking commands."""

from __future__ import annotations

import sys

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from kb.client import RagClient
from kb.config import load_config
from kb.logger import get_logger

logger = get_logger()
console = Console()


@click.group(name="drift")
def drift_group():
    """Check system health and data drift."""


@drift_group.command(name="check")
@click.option("--api-url", default=None, help="RAG API URL override")
@click.option("--qdrant-url", default=None, help="Qdrant URL override")
def check(api_url: str | None, qdrant_url: str | None):
    """Check RAG system health — API, Qdrant, and collection status."""
    cfg = load_config()
    api = cfg["api"]["url"] if not api_url else api_url
    qdrant = cfg["qdrant"]["url"] if not qdrant_url else qdrant_url

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Check API
        task_api = progress.add_task("Checking RAG API...", total=None)
        api_ok, api_data = _check_api(api)
        progress.update(task_api, completed=True)

        # Check Qdrant
        task_qdrant = progress.add_task("Checking Qdrant...", total=None)
        qdrant_ok, qdrant_data = _check_qdrant(qdrant)
        progress.update(task_qdrant, completed=True)

    console.print()

    # Results
    table = Table(title="System Health", show_header=True, header_style="bold")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    table.add_row(
        "RAG API",
        "✅ OK" if api_ok else "❌ Down",
        api if api_ok else f"Not reachable at {api}",
    )

    table.add_row(
        "Qdrant",
        "✅ OK" if qdrant_ok else "❌ Down",
        qdrant if qdrant_ok else f"Not reachable at {qdrant}",
    )

    console.print(table)
    console.print()

    if api_ok and api_data:
        _show_api_details(api_data)

    if qdrant_ok and qdrant_data:
        _show_qdrant_details(qdrant_data)

    if not api_ok and not qdrant_ok:
        console.print(
            Panel(
                "Neither the RAG API nor Qdrant are reachable.\n\n"
                "Start services with: [bold]kb model serve[/bold]\n"
                "Or check the docker-compose status.",
                title="All Systems Down",
                border_style="red",
            )
        )
        sys.exit(1)

    if not qdrant_ok:
        console.print(
            Panel(
                "[yellow]Qdrant is not running.[/yellow]\n"
                "The RAG API may return errors for queries.\n"
                "Start Qdrant with: [bold]kb model serve[/bold]",
                title="Partial Outage",
                border_style="yellow",
            )
        )


@drift_group.command(name="collections")
def collections():
    """List Qdrant collections and their stats."""
    cfg = load_config()
    qdrant_url = cfg["qdrant"]["url"]

    try:
        resp = httpx.get(f"{qdrant_url}/collections", timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        console.print(f"[red]Qdrant not reachable at {qdrant_url}:[/red] {e}")
        sys.exit(1)

    collections_list = data.get("result", {}).get("collections", [])

    if not collections_list:
        console.print("[yellow]No collections found in Qdrant.[/yellow]")
        return

    table = Table(title="Qdrant Collections")
    table.add_column("Name", style="cyan")
    table.add_column("Status")

    for col in collections_list:
        name = col.get("name", "?")
        # Get detail
        try:
            detail = httpx.get(f"{qdrant_url}/collections/{name}", timeout=5)
            detail_data = detail.json().get("result", {})
            status = detail_data.get("status", "?")
            points = detail_data.get("points_count", "?")
            status_str = f"✅ {status} ({points} points)" if status == "green" else f"⚠️ {status}"
        except Exception:
            status_str = "⚠️ Unknown"

        table.add_row(name, status_str)

    console.print(table)


def _check_api(url: str) -> tuple[bool, dict | None]:
    """Check if the RAG API is reachable and healthy."""
    try:
        with RagClient(url) as client:
            health = client.health()
            return health.get("reachable", False), health
    except Exception:
        return False, None


def _check_qdrant(url: str) -> tuple[bool, dict | None]:
    """Check if Qdrant is reachable."""
    try:
        resp = httpx.get(f"{url}/healthz", timeout=5)
        resp.raise_for_status()
        # Get collections info
        col_resp = httpx.get(f"{url}/collections", timeout=5)
        col_data = col_resp.json() if col_resp.is_success else {}
        return True, {"health": "ok", "collections": col_data}
    except Exception as e:
        logger.debug(f"Qdrant check failed: {e}")
        return False, None


def _show_api_details(data: dict):
    """Show RAG API health details."""
    if not data:
        return

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim")
    details.add_column()
    details.add_row("Status", data.get("status", "unknown"))
    details.add_row("Version", data.get("version", "?"))
    details.add_row("Model loaded", "✅" if data.get("model_loaded") else "❌")
    details.add_row("Qdrant points", str(data.get("qdrant_points", 0)))

    console.print(Panel(details, title="RAG API Details", border_style="blue"))


def _show_qdrant_details(data: dict):
    """Show Qdrant health details."""
    collections = data.get("collections", {}).get("result", {}).get("collections", [])
    collection_names = [c.get("name", "?") for c in collections]

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim")
    details.add_column()
    details.add_row("Health", data.get("health", "ok"))
    details.add_row("Collections", ", ".join(collection_names) or "(none)")

    console.print(Panel(details, title="Qdrant Details", border_style="blue"))
