"""Demo web app: FastAPI backend + one static HTML page.

    uvicorn api.app:app --reload            # http://127.0.0.1:8000
    MEDBOT_MOCK_LLM=1 uvicorn api.app:app   # offline, labelled stub replies

Endpoints:
  GET  /               the demo page (api/static/index.html)
  GET  /api/health     liveness/readiness for Docker and hosting platforms: status, mock mode,
                       model IDs, whether an API key is configured (never the key), indexes, risk tools
  GET  /api/schema     agents + risk-tool input fields (for the form)
  GET  /api/example/{organ}   one real row from a trained model's UCI dataset (cardiac only;
                              calculators have no dataset)
  POST /api/ask        {"question": "...", "patient_values": {...}} -> full trace

All model calls still go through orchestrator/client.py via the router; this
module only serialises what the router returns.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from importlib import import_module
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agents.registry import AGENT_CONFIGS, ORGANS
from models.common import DISCLAIMER, row_to_values
from models.tool import RISK_ORGANS, TRAINED_MODELS, has_risk_model, required_inputs, tool_info
from orchestrator import client as llm
from orchestrator.client import AGENT_MODEL, ORCHESTRATOR_MODEL, mock_enabled
from orchestrator.router import handle_query
from rag.ingest import INDEX_DIR, build_index

STATIC = Path(__file__).resolve().parent / "static"



@asynccontextmanager
async def lifespan(_: FastAPI):
    """A fresh deploy has no rag/index/ (it's gitignored); build what's missing."""
    for organ in ORGANS:
        if not (Path(INDEX_DIR) / f"{organ}.faiss").exists():
            build_index(organ)
    yield


app = FastAPI(title="MedBot Orchestrator", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    patient_values: dict[str, str | float | int | None] | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    """Always 200 while the process serves requests. `ready` says whether
    questions can be answered: mock mode, or live with a key configured.
    Reports only whether a key is set, never any part of it."""
    indexes_ready = all((Path(INDEX_DIR) / f"{o}.faiss").exists() for o in ORGANS)
    key_set = bool(llm.NEBIUS_API_KEY)
    return {
        "status": "ok",
        "ready": indexes_ready and (mock_enabled() or key_set),
        "mock": mock_enabled(),
        "api_key_configured": key_set,
        "indexes_ready": indexes_ready,
        "orchestrator_model": ORCHESTRATOR_MODEL,
        "agent_model": AGENT_MODEL,
        "risk_models": [o for o in RISK_ORGANS if has_risk_model(o)],
    }


@app.get("/api/schema")
def schema() -> dict:
    risk = {}
    for organ in RISK_ORGANS:
        if not has_risk_model(organ):
            continue
        risk[organ] = {**tool_info(organ), "fields": required_inputs(organ)}
    return {
        "agents": {o: {"display_name": c["display_name"], "scope": c["scope"]} for o, c in AGENT_CONFIGS.items()},
        "risk_models": risk,
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/example/{organ}")
def example(organ: str, row: int = 0) -> dict:
    """A real, complete row from the model's training dataset — so the demo
    never needs invented patient values."""
    if organ not in TRAINED_MODELS:
        raise HTTPException(404, f"No trained model with a dataset for '{organ}'")
    m = import_module(f"models.{organ}.train")
    X, y = m.load()
    complete = X[m.SPEC.keys].dropna()
    if not 0 <= row < len(complete):
        raise HTTPException(404, f"row must be 0-{len(complete) - 1}")
    return {
        "values": row_to_values(m.SPEC, complete.iloc[row]),
        "source": f"Real row {complete.index[row]} of {m.SPEC.dataset} ({m.SPEC.doi})",
    }


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    values = {k: v for k, v in (req.patient_values or {}).items() if v not in (None, "")} or None
    start = time.perf_counter()
    try:
        r = handle_query(req.question.strip(), patient_values=values)
    except Exception as e:  # model service down, key missing/rejected, network
        status = getattr(e, "status_code", None)
        raise HTTPException(503, llm.redact(
            f"The model service is unavailable ({type(e).__name__}" + (f", HTTP {status}" if status else "") + f"): {e}"))
    total_ms = round((time.perf_counter() - start) * 1000)
    agent_calls = [a.call for a in r.agent_answers.values() if a.call]
    routing = [c for c in r.calls if c["step"] == "Routing"]
    synthesis = [c for c in r.calls if c["step"] == "Synthesis"]
    return {
        "mock": mock_enabled(),
        "query": r.query,
        "routing_method": r.routing_method,
        "agents_consulted": r.agents_consulted,
        "deferred": r.deferred,
        "needs_clarification": r.needs_clarification,
        "final_answer": r.final_answer,
        "total_ms": total_ms,
        "model_calls": routing + agent_calls + synthesis,  # in pipeline order; agents run in parallel
        "agents": [
            {**asdict(a), "display_name": AGENT_CONFIGS[o]["display_name"]}
            for o, a in r.agent_answers.items()
        ],
    }
