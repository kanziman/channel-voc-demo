"""Local live-search endpoint for the dashboard playground (FastAPI).

Powers real-time hybrid search: a query typed in out/dashboard.html is embedded
here by the SAME fastembed model that built the graph (so query and document
vectors are consistent), then scored against Neo4j's vector + full-text indexes
and fused with RRF.

    uvicorn src.graph.serve:app --port 8756   # or: python -m src.graph.serve

The dashboard fetches this when present (127.0.0.1:SEARCH_PORT) and falls back to
precomputed sample queries when it is not, so the static file always works alone.
CORS is open because the dashboard is opened cross-origin (file:// / static host).
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config
from .retriever import hybrid_search
from ..server.routers import agent as agent_router
from ..server.routers import chat as chat_router
from ..server.routers import graph as graph_router
from ..server.routers import search as search_router

app = FastAPI(title="VOC live hybrid search")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# PHASE3 API routers (thin wrappers over existing modules) mounted on the same app.
app.include_router(search_router.router)
app.include_router(chat_router.router)
app.include_router(graph_router.router)
app.include_router(agent_router.router)


# Keep the stdlib server's {"error": ...} envelope for every failure path so the
# static dashboard (which reads `d.error`) never sees FastAPI's default {"detail"}.
@app.exception_handler(StarletteHTTPException)
def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    msg = "not found" if exc.status_code == 404 else str(exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": msg})


@app.exception_handler(RequestValidationError)
def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "invalid request"})


@app.exception_handler(Exception)
def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # Uniform {"error": ...} envelope for every router's runtime failures
    # (routers call Neo4j/fastembed) — never leak plain-text "Internal Server Error".
    return JSONResponse(status_code=500, content={"error": str(exc)})


class SearchRequest(BaseModel):
    query: str
    k: int = 6


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": config.EMBED_MODEL, "dim": config.EMBED_DIM}


@app.post("/search")
def search(req: SearchRequest):
    query = req.query.strip()
    if not query:
        return JSONResponse(status_code=400, content={"error": "empty query"})
    try:
        return hybrid_search(query, k=req.k)
    except Exception as e:  # never 500 the demo silently — dashboard reads {"error"}
        return JSONResponse(status_code=500, content={"error": str(e)})


def main() -> int:
    print(f"▶ VOC live hybrid search on http://127.0.0.1:{config.SEARCH_PORT}")
    print(f"  model={config.EMBED_MODEL} ({config.EMBED_DIM}d) · dense+fulltext+graph → RRF")
    print("  open out/dashboard.html and use the search playground.  Ctrl-C to stop.")
    uvicorn.run(app, host="127.0.0.1", port=config.SEARCH_PORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
