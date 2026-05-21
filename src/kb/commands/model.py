"""kb model — Model serving commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from kb.config import load_config
from kb.logger import get_logger

logger = get_logger()
console = Console()


@click.group(name="model")
def model_group():
    """Manage the RAG API model server."""


@model_group.command(name="serve")
@click.option("--profile", default="", help="docker compose profile (e.g., ingest)")
@click.option(
    "-p", "--project-dir",
    default=None,
    help="Path to rag-devops-assistant project (with docker-compose.yml)",
)
@click.option("--build", is_flag=True, help="Rebuild images before starting")
@click.option("--detach", "-d", is_flag=True, default=True, help="Run in background")
def serve(profile: str, project_dir: str | None, build: bool, detach: bool):
    """Start the RAG API server via Docker Compose.

    Requires the rag-devops-assistant repo with docker-compose.yml.
    """
    cfg = load_config()
    project_path = project_dir or cfg.get("docker_compose", {}).get("project_dir", "")

    if not project_path:
        # Auto-discover: check common locations
        candidates = [
            Path.cwd(),
            Path.home() / "rag-devops-assistant",
            Path.home() / "devops-rag",
        ]
        for c in candidates:
            if (c / "docker-compose.yml").exists():
                project_path = str(c)
                break

    if not project_path or not (Path(project_path) / "docker-compose.yml").exists():
        console.print(
            Panel(
                "[red]Could not find docker-compose.yml[/red]\n\n"
                "Pass [bold]--project-dir[/bold] or set [bold]KB_PROJECT_DIR[/bold] env var.\n"
                "Or clone the rag-devops-assistant repo and point there.",
                title="Project Directory Required",
                border_style="red",
            )
        )
        sys.exit(1)

    cmd = ["docker", "compose"]

    if profile:
        cmd.extend(["--profile", profile])

    cmd.extend(["up", "-d"] if detach else ["up"])

    if build:
        cmd.append("--build")

    logger.info(f"Starting RAG API in {project_path}: {' '.join(cmd)}")
    console.print(f"[dim]Starting services in {project_path}...[/dim]")

    try:
        subprocess.run(cmd, cwd=project_path, check=True)
        console.print("[green]RAG API started![/green]")
        console.print("  API:    [bold]http://localhost:8000[/bold]")
        console.print("  Qdrant: [bold]http://localhost:6333[/bold]")
        console.print("\nQuery it with: [bold]kb rag query \"your question\"[/bold]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to start services:[/red] {e}")
        sys.exit(1)
    except FileNotFoundError:
        console.print("[red]Docker not found. Is Docker installed?[/red]")
        sys.exit(1)


@model_group.command(name="stop")
def stop():
    """Stop the RAG API server."""
    candidates = [
        Path.cwd(),
        Path.home() / "rag-devops-assistant",
    ]
    project_path = None
    for c in candidates:
        if (c / "docker-compose.yml").exists():
            project_path = str(c)
            break

    if not project_path:
        console.print("[yellow]No docker-compose.yml found. Trying 'docker compose down' in cwd...[/yellow]")
        project_path = str(Path.cwd())

    try:
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_path,
            check=True,
        )
        console.print("[green]Services stopped.[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to stop:[/red] {e}")
        sys.exit(1)
