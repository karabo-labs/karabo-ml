"""Configuration management for kb CLI.

Config is loaded from:
1. Defaults
2. ~/.kb/config.yaml (user config file)
3. Environment variables (KB_* prefix — highest priority)
"""

import os
from pathlib import Path
from typing import Any

import yaml

# Default config path
CONFIG_DIR = Path.home() / ".kb"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# Default values
DEFAULTS: dict[str, Any] = {
    "api": {
        "url": os.getenv("KB_API_URL", "http://localhost:8000"),
        "timeout": 30,
    },
    "qdrant": {
        "url": os.getenv("KB_QDRANT_URL", "http://localhost:6333"),
        "collection": os.getenv("KB_QDRANT_COLLECTION", "devops_docs"),
    },
    "logging": {
        "level": os.getenv("KB_LOG_LEVEL", "INFO"),
        "file": os.getenv("KB_LOG_FILE", str(CONFIG_DIR / "kb.log")),
    },
    "docker_compose": {
        "project_dir": os.getenv("KB_PROJECT_DIR", ""),
    },
}


def load_config() -> dict[str, Any]:
    """Load config from file, merged with defaults + env overrides."""
    config = DEFAULTS.copy()

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            user_config = yaml.safe_load(f) or {}
        _deep_merge(config, user_config)

    # Env overrides at specific keys
    _apply_env_override(config, "KB_API_URL", ["api", "url"])
    _apply_env_override(config, "KB_QDRANT_URL", ["qdrant", "url"])
    _apply_env_override(config, "KB_LOG_LEVEL", ["logging", "level"])
    _apply_env_override(config, "KB_LOG_FILE", ["logging", "file"])
    _apply_env_override(config, "KB_PROJECT_DIR", ["docker_compose", "project_dir"])

    return config


def init_config(force: bool = False) -> str:
    """Create default config file. Returns path to created file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists() and not force:
        return f"{CONFIG_FILE} already exists (use --force to overwrite)"

    config = DEFAULTS.copy()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)

    return str(CONFIG_FILE)


def _deep_merge(base: dict, overrides: dict) -> None:
    """Recursively merge overrides into base dict."""
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _apply_env_override(config: dict, env_key: str, keys: list[str]) -> None:
    """Set config[key] from env var if present."""
    val = os.getenv(env_key)
    if val is not None:
        target = config
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = val
