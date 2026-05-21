# ── kb — Karabo ML CLI ──

**kb** is a polished CLI tool for DevOps RAG — query documentation, check cluster health, and manage your infrastructure, all from the terminal.

```
kb rag query "how to setup ArgoCD"
kb rag chat
kb drift check
kb cluster status
kb config show
```

## Quick Start

### pip install

```bash
pip install karabo-ml
kb --help
```

### Docker

```bash
docker run --rm ghcr.io/dynamickarabo/karabo-ml kb --help
```

### From source

```bash
git clone https://github.com/DynamicKarabo/karabo-ml.git
cd karabo-ml
pip install -e .
kb --help
```

## Commands

### `kb rag query` — Ask a DevOps question

```bash
kb rag query "How do I set up ArgoCD in a k3s cluster?"
kb rag query --top-k 10 --json "What is the best way to configure Prometheus?"
```

### `kb rag chat` — Interactive mode

```bash
kb rag query
# or
kb rag chat
# Then type questions interactively. /exit to quit.
```

### `kb model serve` — Start the RAG API

```bash
kb model serve                 # via docker-compose
kb model serve --build         # rebuild images first
kb model serve --profile ingest  # include ingestion
kb model stop                  # stop services
```

### `kb drift check` — System health

```bash
kb drift check                 # API + Qdrant health
kb drift collections           # list Qdrant collections
```

### `kb cluster status` — Cluster monitoring

```bash
kb cluster status              # Docker + k3s status
kb cluster status --json       # JSON output
kb cluster logs api            # view API logs
kb cluster logs qdrant --tail 200
```

### `kb config` — Configuration

```bash
kb config init                 # create ~/.kb/config.yaml
kb config show                 # view current config
kb config edit                 # open in $EDITOR
```

### `kb completions` — Shell completions

```bash
kb completions install bash    # add to ~/.bashrc
kb completions install zsh     # add to ~/.zshrc
kb completions bash            # print completions script
```

## Configuration

Config loaded from (in priority order):

1. `~/.kb/config.yaml` (defaults)
2. Environment variables (`KB_API_URL`, `KB_QDRANT_URL`, etc.)

Create your config:

```bash
kb config init
```

Example `~/.kb/config.yaml`:

```yaml
api:
  url: http://localhost:8000
  timeout: 30
qdrant:
  url: http://localhost:6333
  collection: devops_docs
logging:
  level: INFO
  file: ~/.kb/kb.log
```

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  kb CLI  │────▶│ RAG API  │────▶│  Qdrant  │
│ (Python) │     │ (FastAPI)│     │(Vectors) │
└──────────┘     └────┬─────┘     └──────────┘
                      │
               ┌──────▼──────┐
               │  OpenRouter │
               │   (LLM)     │
               └─────────────┘

┌──────────┐     ┌──────────┐
│ Web UI   │────▶│ RAG API  │
│(HTMX+FA) │     │ (same)   │
└──────────┘     └──────────┘
```

## Development

```bash
pip install -e ".[dev]"
ruff check src/
ruff format src/
```

## Tech Stack

| Layer | Tool |
|-------|------|
| CLI framework | Click + Rich |
| HTTP client | httpx |
| Config | PyYAML + env vars |
| Backend API | FastAPI + Qdrant |
| LLM | OpenRouter (OpenAI-compatible) |
| Web UI | FastAPI + HTMX + Jinja2 |
| Container | Docker multi-stage |
| Orchestration | Docker Compose / k3s |
| CI/CD | GitHub Actions |
| Distribution | PyPI + GHCR |
