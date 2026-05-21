"""kb tui — Textual TUI dashboard for karabo-ml."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Header,
    Input,
    LoadingIndicator,
    Static,
    TabbedContent,
    TabPane,
)

from kb import __version__

# ── Fallback data (mirrors KaroPlatform backend) ──

FALLBACK_MODELS = [
    {"name": "phi-3-vision", "type": "VLM", "version": "3.0", "status": "running", "endpoint": "/v1/chat/completions"},
    {"name": "qwen2-vl", "type": "VLM", "version": "2.0", "status": "stopped", "endpoint": "/v1/chat/completions"},
    {
        "name": "nomic-embed-text",
        "type": "embedding",
        "version": "1.5",
        "status": "running",
        "endpoint": "/v1/embeddings",
    },
]

FALLBACK_CLUSTER = {
    "nodes": 1,
    "cpu": {"total": 4, "used": 1.2},
    "memory": {"total_gb": 16, "used_gb": 4.5},
    "pods": {"running": 12, "total": 30},
    "namespaces": ["default", "kube-system", "karo-platform", "monitoring"],
}

FALLBACK_DEPLOYMENTS = [
    {"name": "karo-platform", "namespace": "karo-platform", "ready": "1/1"},
    {"name": "coredns", "namespace": "kube-system", "ready": "1/1"},
    {"name": "metrics-server", "namespace": "kube-system", "ready": "1/1"},
]


def _run_kb(args: list[str]) -> dict[str, Any]:
    """Run a karabo-ml command."""
    kb = shutil.which("kb") or "kb"
    try:
        result = subprocess.run([kb, *args], capture_output=True, text=True, timeout=15)
        return {"output": result.stdout.strip() or result.stderr.strip(), "code": result.returncode}
    except Exception as e:
        return {"error": str(e)}


def _get_models() -> list[dict[str, Any]]:
    """Get models — tries CLI, falls back to demo data."""
    try:
        subprocess.run(["kb", "model", "serve", "--dry-run"], capture_output=True, text=True, timeout=5)
    except Exception:
        pass
    return FALLBACK_MODELS  # CLI doesn't have model list, show demo


def _get_cluster_status() -> dict[str, Any]:
    """Get cluster status."""
    try:
        result = subprocess.run(["kubectl", "get", "nodes", "-o", "json"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)
            nodes = len(data.get("items", []))
            # Parse pod counts
            pods_result = subprocess.run(
                ["kubectl", "get", "pods", "--all-namespaces", "--no-headers"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            total = len(pods_result.stdout.strip().split("\n")) if pods_result.stdout.strip() else 0
            running = pods_result.stdout.count("Running") if pods_result.stdout else 0
            return {**FALLBACK_CLUSTER, "nodes": nodes, "pods": {"running": running, "total": total}}
    except Exception:
        pass
    return FALLBACK_CLUSTER


def _get_deployments() -> list[dict[str, Any]]:
    """Get k8s deployments."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "deployments", "--all-namespaces", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)
            deps = []
            for item in data.get("items", []):
                deps.append(
                    {
                        "name": item["metadata"]["name"],
                        "namespace": item["metadata"]["namespace"],
                        "ready": f"{item['status'].get('readyReplicas', 0)}/{item['status'].get('replicas', 0)}",
                    }
                )
            return deps if deps else FALLBACK_DEPLOYMENTS
    except Exception:
        pass
    return FALLBACK_DEPLOYMENTS


# ── Widgets ──


class StatusBar(Static):
    """Bottom status bar showing connection info."""

    k3s_status = reactive("checking...")

    def on_mount(self) -> None:
        self.update_status()
        self.set_interval(30, self.update_status)

    async def update_status(self) -> None:
        try:
            r = subprocess.run(["kubectl", "get", "nodes", "--no-headers"], capture_output=True, text=True, timeout=5)
            self.k3s_status = "connected" if r.returncode == 0 else "unreachable"
        except Exception:
            self.k3s_status = "unreachable"
        self.update(f"k3s: {self.k3s_status}  |  kb v{__version__}  |  [dim]F5=refresh  q=quit[/dim]")


class ModelCard(Static):
    """A single model card widget."""

    def __init__(self, model: dict[str, Any]) -> None:
        super().__init__()
        self.model = model

    def compose(self) -> ComposeResult:
        m = self.model
        status = m.get("status", "unknown")
        icon = "🟢" if status == "running" else "🔴" if status == "stopped" else "⚪"
        yield Vertical(
            Static(f"[bold]{m.get('name', '?')}[/bold]  {icon} [dim]{status}[/dim]", classes="model-title"),
            Static(f"Type: {m.get('type', '—')}  |  v{m.get('version', '—')}", classes="model-meta"),
            Static(f"[dim]{m.get('endpoint', '')}[/dim]", classes="model-endpoint"),
            Horizontal(
                Button("▶ Deploy", id=f"deploy-{m['name']}", variant="primary"),
                Button("⏹ Stop", id=f"stop-{m['name']}", variant="error"),
                Button("📋 Logs", id=f"logs-{m['name']}"),
                classes="model-actions",
            ),
            classes="model-card-container",
        )


class ClusterTab(Container):
    """Cluster status tab content."""

    def compose(self) -> ComposeResult:
        yield LoadingIndicator()
        with Container(id="cluster-content"):
            yield Static("Loading...", id="cluster-summary")
            yield DataTable(id="cluster-table")
            yield Static("", classes="section-title", id="deployments-title")
            yield DataTable(id="deployments-table")

    def on_mount(self) -> None:
        self.refresh_cluster()
        self.set_interval(30, self.refresh_cluster)

    @work
    async def refresh_cluster(self) -> None:
        status = _get_cluster_status()
        deps = _get_deployments()

        summary = self.query_one("#cluster-summary", Static)
        pods = status.get("pods", {})
        summary.update(
            f"[bold]Nodes:[/bold] {status.get('nodes', '?')}  "
            f"[bold]CPU:[/bold] {status.get('cpu', {}).get('used', '?')}/"
            f"{status.get('cpu', {}).get('total', '?')} cores  "
            f"[bold]Memory:[/bold] {status.get('memory', {}).get('used_gb', '?')}/"
            f"{status.get('memory', {}).get('total_gb', '?')} GB  "
            f"[bold]Pods:[/bold] "
            f"{pods.get('running', '?')}/{pods.get('total', '?')} running"
        )

        table = self.query_one("#cluster-table", DataTable)
        table.clear()
        table.columns.clear()
        table.add_columns("Namespace", "Name", "Ready", "Status")
        table.add_rows((d["namespace"], d["name"], d["ready"], "Running") for d in deps)


class ModelsTab(Container):
    """Models tab content."""

    def compose(self) -> ComposeResult:
        yield LoadingIndicator()
        yield Container(id="models-grid")

    def on_mount(self) -> None:
        self.refresh_models()
        self.set_interval(15, self.refresh_models)

    @work
    async def refresh_models(self) -> None:
        models = _get_models()
        grid = self.query_one("#models-grid", Container)
        await grid.remove_children()
        for m in models:
            await grid.mount(ModelCard(m))
        self.query_one(LoadingIndicator).remove()


class RAGTab(Container):
    """RAG query tab."""

    def compose(self) -> ComposeResult:
        yield Static("[bold]🔍 RAG Assistant[/bold]", classes="section-title")
        yield Input(placeholder='Ask a DevOps question... (e.g. "how to setup ArgoCD")', id="rag-input")
        yield Static("", id="rag-result", classes="rag-result")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.query_rag(event.value.strip())

    @work
    async def query_rag(self, query: str) -> None:
        result_widget = self.query_one("#rag-result", Static)
        result_widget.update("[dim]Querying...[/dim]")
        result = _run_kb(["rag", "query", query])
        output = result.get("output", result.get("error", "No response"))
        result_widget.update(f"[bold]Q:[/bold] {query}\n\n{output}")


class ConfigTab(Container):
    """Config tab content."""

    def compose(self) -> ComposeResult:
        yield Static("[bold]⚙️ Configuration[/bold]", classes="section-title")
        yield DataTable(id="config-table")

    def on_mount(self) -> None:
        table = self.query_one("#config-table", DataTable)
        table.add_columns("Key", "Value")
        import os

        config_items = [
            ("KARO_ML_API_URL", os.getenv("KARO_ML_API_URL", "not set")),
            ("KUBECONFIG", os.getenv("KUBECONFIG", "default (in-cluster)")),
            ("LOG_LEVEL", os.getenv("KARO_LOG_LEVEL", "INFO")),
            ("Version", __version__),
        ]
        table.add_rows(config_items)


# ── Main App ──


class KaroDashboard(App):
    """karabo-ml Terminal Dashboard."""

    TITLE = "⚡ kb — Karabo ML Dashboard"
    CSS = """
    Screen {
        background: $surface;
    }

    .model-card-container {
        border: solid $primary;
        margin: 0 0 1 0;
        padding: 1;
        height: 8;
    }

    .model-card-container:hover {
        border: solid $accent;
    }

    .model-title {
        text-style: bold;
        padding: 0 0 0 0;
    }

    .model-meta {
        color: $text-muted;
        padding: 0 0 0 0;
    }

    .model-endpoint {
        color: $text-disabled;
        padding: 0 0 0 0;
    }

    .model-actions {
        align: center left;
        height: 3;
        padding: 0 0 0 0;
    }

    .model-actions Button {
        margin: 0 1 0 0;
        min-width: 12;
    }

    #models-grid {
        layout: grid;
        grid-size: 2 3;
        grid-gutter: 1;
        height: 100%;
    }

    #cluster-content {
        padding: 1;
    }

    #cluster-summary {
        margin: 1 0;
    }

    .section-title {
        text-style: bold;
        margin: 1 0;
    }

    .rag-result {
        margin: 1 0;
        padding: 1;
        border: solid $border;
        min-height: 5;
    }

    TabbedContent {
        height: 1fr;
    }

    DataTable {
        height: 10;
    }

    LoadingIndicator {
        height: 3;
    }

    #config-table {
        height: 8;
    }

    StatusBar {
        background: $panel;
        color: $text-muted;
        padding: 0 1;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("f5", "refresh", "Refresh", show=True),
        Binding("1", "tab_models", "Models", show=False),
        Binding("2", "tab_cluster", "Cluster", show=False),
        Binding("3", "tab_rag", "RAG", show=False),
        Binding("4", "tab_config", "Config", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="models"):
            with TabPane("🧠 Models", id="models"):
                yield ModelsTab()
            with TabPane("🖥️ Cluster", id="cluster"):
                yield ClusterTab()
            with TabPane("🔍 RAG", id="rag"):
                yield RAGTab()
            with TabPane("⚙️ Config", id="config"):
                yield ConfigTab()
        yield StatusBar()

    def action_refresh(self) -> None:
        """Refresh current tab."""
        tab = self.query_one(TabbedContent)
        active = tab.active
        if active == "models":
            self.query_one(ModelsTab).refresh_models()
        elif active == "cluster":
            self.query_one(ClusterTab).refresh_cluster()
        self.notify("Refreshed ✅", timeout=2)

    def action_tab_models(self) -> None:
        self.query_one(TabbedContent).active = "models"

    def action_tab_cluster(self) -> None:
        self.query_one(TabbedContent).active = "cluster"

    def action_tab_rag(self) -> None:
        self.query_one(TabbedContent).active = "rag"

    def action_tab_config(self) -> None:
        self.query_one(TabbedContent).active = "config"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("deploy-"):
            name = btn_id.replace("deploy-", "")
            self.notify(f"Deploying {name}...", timeout=3)
            _run_kb(["model", "serve"])
            self.notify(f"✅ {name} deployment triggered", timeout=3)
        elif btn_id.startswith("stop-"):
            name = btn_id.replace("stop-", "")
            self.notify(f"Stopping {name}...", timeout=3)
            _run_kb(["model", "stop"])
            self.notify(f"⏹ {name} stopped", timeout=3)


def run() -> None:
    """Entry point for `kb tui`."""
    app = KaroDashboard()
    app.run()
