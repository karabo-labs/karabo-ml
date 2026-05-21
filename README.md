# kb -- Karabo ML CLI

DevOps RAG CLI. Query documentation, check cluster health, manage infrastructure from the terminal.

```
kb rag query "how to setup ArgoCD"
kb rag chat
kb drift check
kb cluster status
kb config show
```

## Quick Start

**pip install**
```bash
pip install karabo-ml
```
Output: Installs `kb` CLI. Run `kb --help` to verify.

**Docker**
```bash
docker run --rm ghcr.io/dynamickarabo/karabo-ml --help
```
Output: CLI help text. Container exits after execution.

**From source**
```bash
git clone https://github.com/DynamicKarabo/karabo-ml.git
cd karabo-ml
pip install -e .
```
Output: Editable install. Run `kb --help` to verify.

## Commands

### rag -- Documentation queries

**Query** -- Ask a DevOps question against indexed docs.
```bash
kb rag query "How do I set up ArgoCD in a k3s cluster?"
```
Output: Synthesised answer with citations from indexed documentation.

```bash
kb rag query --top-k 10 --json "What is the best way to configure Prometheus?"
```
Output: JSON response with top-10 relevant chunks and answer.

**Chat** -- Interactive multi-turn Q&A.
```bash
kb rag chat
```
Output: Interactive prompt. Type questions, receive answers. `/exit` to quit.

### model -- RAG API lifecycle

**Serve** -- Start the RAG backend (FastAPI + Qdrant).
```bash
kb model serve                 # via docker-compose
kb model serve --build         # rebuild images first
kb model serve --profile ingest  # include ingestion pipeline
```
Output: Container logs streaming to terminal. API available at http://localhost:8000.

**Stop** -- Tear down services.
```bash
kb model stop
```
Output: Containers stopped and removed.

### drift -- Health checks

**Check** -- Verify API + Qdrant are reachable.
```bash
kb drift check
```
Output: Health status for each service (OK / FAIL).

**Collections** -- List Qdrant vector collections.
```bash
kb drift collections
```
Output: Table of collection names and metadata.

### cluster -- Infrastructure monitoring

**Status** -- Show Docker + k3s cluster state.
```bash
kb cluster status
```
Output: Table with services, status, resource usage.

```bash
kb cluster status --json
```
Output: Same data in JSON format.

**Logs** -- View service logs.
```bash
kb cluster logs api
kb cluster logs qdrant --tail 200
```
Output: Log lines from the specified service. Tail count defaults to 50.

### config -- Settings management

**Init** -- Create default config file.
```bash
kb config init
```
Output: Writes `~/.kb/config.yaml` with defaults. No stdout output.

**Show** -- Print current effective configuration.
```bash
kb config show
```
Output: YAML-formatted merged config (file + env overrides).

**Edit** -- Open config in `$EDITOR`.
```bash
kb config edit
```
Output: Opens `~/.kb/config.yaml` in your editor. Saves on write.

### completions -- Shell tab-completions

**Install** -- Register completions permanently.
```bash
kb completions install bash    # appends to ~/.bashrc
kb completions install zsh     # appends to ~/.zshrc
```
Output: Completions appended to shell rc file. Restart shell or source to activate.

**Print** -- Output completions script to stdout.
```bash
kb completions bash            # print script without installing
```
Output: Shell completions script. Pipe to `source` or eval for immediate use.

## Configuration

Config loaded in priority order:
1. `~/.kb/config.yaml` (defaults)
2. Environment variables (overrides file values)

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

Environment variables map to config keys: `KB_API_URL`, `KB_QDRANT_URL`, `KB_LOG_LEVEL`, etc.

## Architecture

```
kb CLI  ---- RAG API (FastAPI) ---- Qdrant (vectors)
          \                      \
           \-- OpenRouter (LLM)   \-- Web UI (HTMX)
```

Data flow: `kb rag query` -> RAG API -> retrieve from Qdrant -> augment prompt -> call OpenRouter -> return answer. Web UI uses same API on the backend.

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
