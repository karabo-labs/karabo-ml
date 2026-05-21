from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from kb.client import RagClient
from kb.config import load_config

app = FastAPI(title="kb — Karabo ML Web UI", version="0.2.0")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
static = Path(__file__).parent / "static"


def get_client() -> RagClient:
    cfg = load_config()
    return RagClient(base_url=cfg["api"]["url"], timeout=cfg["api"]["timeout"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "answer": None, "question": ""},
    )


@app.post("/query", response_class=HTMLResponse)
async def query(request: Request, question: str = Form(...)):
    try:
        with get_client() as client:
            result = client.query(question, top_k=5, include_sources=True)
    except Exception as e:
        result = {"error": str(e), "answer": "", "sources": [], "tokens_used": 0}

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "question": question,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "tokens_used": result.get("tokens_used", 0),
            "model": result.get("model", ""),
            "latency_ms": result.get("latency_ms", 0),
            "error": result.get("error"),
        },
    )


@app.get("/health")
async def health():
    try:
        with get_client() as client:
            return client.health()
    except Exception as e:
        return {"status": "error", "error": str(e)}
