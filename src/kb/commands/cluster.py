"""kb cluster — Cluster status commands."""

from __future__ import annotations

import shutil
import subprocess
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kb.config import load_config
from kb.logger import get_logger

logger = get_logger()
console = Console()


@click.group(name="cluster")
def cluster_group():
    """Check k3s / Docker cluster status."""


@cluster_group.command(name="status")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all containers, not just rag-*")
@click.option("--json", "json_output", is_flag=True, help="Output raw JSON")
def status(show_all: bool, json_output: bool):
    """Check cluster status — Docker containers and k3s if available."""
    if json_output:
        import json as _json

        data = {
            "docker": _get_docker_status(show_all),
            "k3s": _get_k3s_status(),
        }
        console.print(_json.dumps(data, indent=2))
        return

    # Docker status
    containers = _get_docker_status(show_all)

    table = Table(
        title=f"{'All' if show_all else 'RAG'} Containers",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Name")
    table.add_column("Image")
    table.add_column("Status")
    table.add_column("Ports")

    for c in containers:
        name = c.get("name", "?")
        image = c.get("image", "?")[:40]
        st = c.get("status", "?")
        status_icon = "✅" if "Up" in st else "❌"
        ports = c.get("ports", "-")
        table.add_row(f"{status_icon} {name}", image, st, ports)

    if containers:
        console.print(table)
    else:
        if show_all:
            console.print("[yellow]No containers running.[/yellow]")
        else:
            console.print("[yellow]No RAG containers found. Start with: kb model serve[/yellow]")

    # k3s status
    k3s = _get_k3s_status()
    if k3s.get("available"):
        k3s_table = Table(title="k3s Cluster", show_header=True, header_style="bold cyan")
        k3s_table.add_column("Resource")
        k3s_table.add_column("Status")

        for ns in k3s.get("namespaces", []):
            k3s_table.add_row(f"Namespace: {ns['name']}", f"{ns['pods_ready']}/{ns['pods_total']} pods ready")

        if k3s.get("nodes"):
            for node in k3s["nodes"]:
                k3s_table.add_row(f"Node: {node['name']}", node["status"])

        console.print(k3s_table)
    elif k3s.get("installed") is False:
        console.print("[dim]k3s not installed. Using Docker Compose for deployment.[/dim]")
    else:
        console.print("[dim]k3s not reachable (permission or config issue).[/dim]")


@cluster_group.command(name="logs")
@click.argument("service", required=False, default="api")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--tail", default=50, help="Number of lines to show")
def logs(service: str, follow: bool, tail: int):
    """Show logs from a RAG service container."""
    cmd = ["docker", "logs"]

    if follow:
        cmd.append("--follow")

    cmd.extend(["--tail", str(tail)])

    # Map service name to container
    container_map = {
        "api": "rag-api",
        "qdrant": "rag-qdrant",
        "ingest": "rag-ingest",
    }

    container = container_map.get(service, service)
    cmd.append(container)

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to get logs for '{container}':[/red] {e}")
        sys.exit(1)
    except FileNotFoundError:
        console.print("[red]Docker not found.[/red]")
        sys.exit(1)


def _get_docker_status(show_all: bool) -> list[dict]:
    """Get Docker container status."""
    try:
        if not shutil.which("docker"):
            return []

        format_str = "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
        result = subprocess.run(
            ["docker", "ps", "--format", format_str],
            capture_output=True, text=True, timeout=10,
        )

        if result.returncode != 0:
            return []

        containers = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t", 3)
            if len(parts) == 4:
                name, image, status, ports = parts
                if show_all or "rag" in name:
                    containers.append({
                        "name": name,
                        "image": image,
                        "status": status,
                        "ports": ports,
                    })

        return containers
    except Exception as e:
        logger.debug(f"Docker status check failed: {e}")
        return []


def _get_k3s_status() -> dict:
    """Check k3s availability and status."""
    result = {"available": False, "installed": False, "nodes": [], "namespaces": []}

    try:
        if not shutil.which("kubectl"):
            result["installed"] = False
            return result

        result["installed"] = True

        # Check if k3s context is accessible
        ctx = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True, text=True, timeout=5,
        )
        if ctx.returncode != 0:
            return result

        result["available"] = True

        # Get nodes
        nodes_out = subprocess.run(
            ["kubectl", "get", "nodes", "-o", "json"],
            capture_output=True, text=True, timeout=10,
        )
        if nodes_out.returncode == 0:
            import json
            nodes_data = json.loads(nodes_out.stdout)
            for node in nodes_data.get("items", []):
                name = node["metadata"]["name"]
                conditions = {c["type"]: c["status"] for c in node.get("status", {}).get("conditions", [])}
                status = "Ready" if conditions.get("Ready") == "True" else "Not Ready"
                result["nodes"].append({"name": name, "status": status})

        # Get namespaces with pods
        pods_out = subprocess.run(
            ["kubectl", "get", "pods", "--all-namespaces", "-o", "json"],
            capture_output=True, text=True, timeout=10,
        )
        if pods_out.returncode == 0:
            import json
            pods_data = json.loads(pods_out.stdout)
            ns_map = {}
            for pod in pods_data.get("items", []):
                ns = pod["metadata"]["namespace"]
                if ns not in ns_map:
                    ns_map[ns] = {"total": 0, "ready": 0}

                ns_map[ns]["total"] += 1
                container_statuses = pod.get("status", {}).get("containerStatuses", [])
                all_ready = all(cs.get("ready") for cs in container_statuses)
                if all_ready:
                    ns_map[ns]["ready"] += 1

            for ns, counts in ns_map.items():
                result["namespaces"].append({
                    "name": ns,
                    "pods_total": counts["total"],
                    "pods_ready": counts["ready"],
                })

    except Exception as e:
        logger.debug(f"k3s status check failed: {e}")

    return result
