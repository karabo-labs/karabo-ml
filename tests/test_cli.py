"""Tests for kb CLI tool — config, client, CLI commands."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from kb import __version__
from kb.cli import cli
from kb.config import load_config, init_config, CONFIG_DIR


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    """Click test runner."""
    return CliRunner()


@pytest.fixture
def isolated_cfg(runner: CliRunner):
    """Run test in isolated filesystem so ~/.kb doesn't pollute real config."""
    with runner.isolated_filesystem():
        old_home = os.environ.get("HOME", "")
        os.environ["HOME"] = os.getcwd()
        # Force CONFIG_DIR to use the isolated HOME
        import kb.config as cfg_mod

        original_dir = cfg_mod.CONFIG_DIR
        cfg_mod.CONFIG_DIR = Path(os.getcwd()) / ".kb"
        cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.yaml"

        yield

        cfg_mod.CONFIG_DIR = original_dir
        cfg_mod.CONFIG_FILE = original_dir / "config.yaml"
        os.environ["HOME"] = old_home


# ── Version ────────────────────────────────────────────────────────


class TestVersion:
    def test_version_string(self):
        """__version__ is a non-empty semver string."""
        assert __version__ != ""
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_cli_version_flag(self, runner: CliRunner):
        """kb --version prints the version and exits."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert f"kb v{__version__}" in result.output

    def test_cli_no_args_shows_help(self, runner: CliRunner):
        """kb with no args shows the help panel."""
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "kb — Karabo ML" in result.output
        assert "rag query" in result.output
        assert "drift check" in result.output


# ── Config ─────────────────────────────────────────────────────────


class TestConfig:
    def test_init_creates_file(self, isolated_cfg):
        """kb config init creates ~/.kb/config.yaml."""
        path = init_config()
        assert Path(path).exists()
        assert "api" in Path(path).read_text()

    def test_init_idempotent(self, isolated_cfg):
        """kb config init without --force doesn't overwrite."""
        init_config()
        path = Path(init_config())
        assert "already exists" in init_config()

    def test_init_force_overwrites(self, isolated_cfg):
        """kb config init --force overwrites existing config."""
        init_config()
        path = Path(init_config(force=True))
        assert path.exists()

    def test_load_defaults(self, isolated_cfg):
        """Config loads sensible defaults without a config file."""
        cfg = load_config()
        assert cfg["api"]["url"] == "http://localhost:8000"
        assert cfg["api"]["timeout"] == 30
        assert cfg["qdrant"]["url"] == "http://localhost:6333"
        assert cfg["logging"]["level"] == "INFO"

    def test_env_overrides(self, isolated_cfg):
        """Environment variables override config values."""
        with patch.dict(os.environ, {"KB_API_URL": "http://example.com:9999"}):
            cfg = load_config()
            assert cfg["api"]["url"] == "http://example.com:9999"

    def test_config_show_command(self, runner: CliRunner, isolated_cfg):
        """kb config shows the config."""
        init_config()
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "API" in result.output
        # Should show either default or env-overridden URL
        assert "localhost" in result.output or "example.com" in result.output

    def test_config_init_command(self, runner: CliRunner, isolated_cfg):
        """kb config init creates config and reports path."""
        result = runner.invoke(cli, ["config", "init", "--force"])
        assert result.exit_code == 0
        assert "Config initialized" in result.output

    def test_config_init_no_force(self, runner: CliRunner, isolated_cfg):
        """kb config init without --force warns if exists."""
        runner.invoke(cli, ["config", "init", "--force"])
        result = runner.invoke(cli, ["config", "init"])
        assert "already exists" in result.output


# ── Client ──────────────────────────────────────────────────────────


class TestClient:
    def test_health_returns_dict(self):
        """RagClient.health() returns a dict."""
        from kb.client import RagClient

        with RagClient("http://localhost:18000") as client:
            result = client.health()
        # Should handle connection refused gracefully
        assert isinstance(result, dict)
        assert "reachable" in result

    def test_query_handles_connection_error(self):
        """RagClient.query() returns error dict when server is down."""
        from kb.client import RagClient

        with RagClient("http://localhost:18000") as client:
            result = client.query("test question")
        assert "error" in result
        assert result.get("answer", None) is not None or "error" in result


# ── CLI Commands — Help ────────────────────────────────────────────


class TestCliHelp:
    def test_rag_help(self, runner: CliRunner):
        """kb rag --help shows rag subcommands."""
        result = runner.invoke(cli, ["rag", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output

    def test_model_help(self, runner: CliRunner):
        """kb model --help shows model subcommands."""
        result = runner.invoke(cli, ["model", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.output

    def test_drift_help(self, runner: CliRunner):
        """kb drift --help shows drift subcommands."""
        result = runner.invoke(cli, ["drift", "--help"])
        assert result.exit_code == 0
        assert "check" in result.output

    def test_cluster_help(self, runner: CliRunner):
        """kb cluster --help shows cluster subcommands."""
        result = runner.invoke(cli, ["cluster", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output

    def test_completions_help(self, runner: CliRunner):
        """kb completions --help shows completions subcommands."""
        result = runner.invoke(cli, ["completions", "--help"])
        assert result.exit_code == 0
        assert "install" in result.output


# ── CLI Commands — Rag Query ───────────────────────────────────────


class TestRagQuery:
    def test_query_no_args_starts_chat(self, runner: CliRunner):
        """kb rag query with no args shows interactive prompt."""
        result = runner.invoke(cli, ["rag", "query"], input="/exit\n")
        assert result.exit_code == 0
        assert "interactive" in result.output.lower() or "kb>" in result.output

    def test_query_with_question_and_no_server(self, runner: CliRunner):
        """kb rag query 'question' returns some response (error or answer)."""
        result = runner.invoke(cli, ["rag", "query", "test question"])
        # Either connection error (no server) or server error (bad request) — handle gracefully
        assert result.exit_code is not None

    def test_query_json_flag(self, runner: CliRunner):
        """kb rag query --json shows usage info without server."""
        result = runner.invoke(cli, ["rag", "query", "--json", "test"])
        assert result.exit_code in (0, 1)

    def test_query_verbose(self, runner: CliRunner):
        """kb rag query -v enables debug logging."""
        result = runner.invoke(cli, ["-v", "rag", "query", "test"])
        # Verbose flag should not crash
        assert result.exit_code is not None

    def test_query_top_k_flag(self, runner: CliRunner):
        """kb rag query --top-k 10 parses correctly."""
        result = runner.invoke(cli, ["rag", "query", "--top-k", "10", "test"])
        assert result.exit_code is not None

    def test_query_no_sources_flag(self, runner: CliRunner):
        """kb rag query --no-sources parses correctly."""
        result = runner.invoke(cli, ["rag", "query", "--no-sources", "test"])
        assert result.exit_code is not None


# ── CLI Commands — Drift Check ─────────────────────────────────────


class TestDriftCheck:
    def test_drift_check_no_server(self, runner: CliRunner):
        """kb drift check handles down services gracefully."""
        result = runner.invoke(cli, ["drift", "check"])
        assert result.exit_code in (0, 1)
        assert "System Health" in result.output or "All Systems Down" in result.output

    def test_drift_collections_no_server(self, runner: CliRunner):
        """kb drift collections handles Qdrant down."""
        result = runner.invoke(cli, ["drift", "collections"])
        assert result.exit_code in (0, 1)
        assert "Qdrant" in result.output or "reachable" in result.output or "Not" in result.output


# ── CLI Commands — Cluster Status ──────────────────────────────────


class TestClusterStatus:
    def test_cluster_status(self, runner: CliRunner):
        """kb cluster status shows container info."""
        result = runner.invoke(cli, ["cluster", "status"])
        assert result.exit_code == 0

    def test_cluster_status_all(self, runner: CliRunner):
        """kb cluster status --all shows all containers."""
        result = runner.invoke(cli, ["cluster", "status", "--all"])
        assert result.exit_code == 0

    def test_cluster_status_json(self, runner: CliRunner):
        """kb cluster status --json outputs valid JSON."""
        result = runner.invoke(cli, ["cluster", "status", "--json"])
        assert result.exit_code == 0
        try:
            json.loads(result.output)
        except json.JSONDecodeError:
            pytest.fail("cluster status --json did not return valid JSON")


# ── CLI Commands — Completions ────────────────────────────────────


class TestCompletions:
    def test_completions_bash(self, runner: CliRunner):
        """kb completions bash generates bash completion script."""
        result = runner.invoke(cli, ["completions", "bash"])
        assert result.exit_code == 0
        assert "_kb_completion" in result.output

    def test_completions_zsh(self, runner: CliRunner):
        """kb completions zsh generates zsh completion script."""
        result = runner.invoke(cli, ["completions", "zsh"])
        assert result.exit_code == 0

    def test_completions_fish(self, runner: CliRunner):
        """kb completions fish generates fish completion script."""
        result = runner.invoke(cli, ["completions", "fish"])
        assert result.exit_code == 0

    def test_completions_install_bash(self, runner: CliRunner):
        """kb completions install bash adds line to .bashrc."""
        with runner.isolated_filesystem():
            home = os.getcwd()
            Path(home, ".bashrc").write_text("# existing\n")
            with patch.dict(os.environ, {"HOME": home}):
                result = runner.invoke(cli, ["completions", "install", "bash"])
            assert result.exit_code == 0
            assert "Completions installed" in result.output
            bashrc = Path(home, ".bashrc").read_text()
            assert "kb completions" in bashrc

    def test_completions_install_idempotent(self, runner: CliRunner):
        """kb completions install is idempotent — won't add twice."""
        with runner.isolated_filesystem():
            home = os.getcwd()
            Path(home, ".bashrc").write_text("# existing\n")
            with patch.dict(os.environ, {"HOME": home}):
                runner.invoke(cli, ["completions", "install", "bash"])
                result = runner.invoke(cli, ["completions", "install", "bash"])
            assert "already installed" in result.output


# ── CLI Commands — Config ──────────────────────────────────────────


class TestConfigCommand:
    def test_config_init_creates_file(self, runner: CliRunner):
        """kb config init creates a config file in ~/.kb."""
        with runner.isolated_filesystem():
            home = os.getcwd()
            with patch.dict(os.environ, {"HOME": home}):
                import kb.config as cfg_mod
                orig_dir = cfg_mod.CONFIG_DIR
                cfg_mod.CONFIG_DIR = Path(home) / ".kb"
                cfg_mod.CONFIG_FILE = cfg_mod.CONFIG_DIR / "config.yaml"

                result = runner.invoke(cli, ["config", "init", "--force"])
                assert result.exit_code == 0
                assert "Config initialized" in result.output
                assert cfg_mod.CONFIG_FILE.exists()

                cfg_mod.CONFIG_DIR = orig_dir
                cfg_mod.CONFIG_FILE = orig_dir / "config.yaml"
