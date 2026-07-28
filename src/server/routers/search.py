"""POST /api/search/hybrid — thin adapter over retriever.hybrid_search (§3.1 [WRAP]).

No new retrieval logic: the router validates the request, calls the existing
triple-arm hybrid search, and shapes the response with a Pydantic model so the
per-result arms/rrf contract is explicit for the chatbot + 3-column console.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ...graph.retriever import hybrid_search

router = APIRouter(prefix="/api/search", tags=["search"])


class HybridSearchRequest(BaseModel):
    query: str
    k: int = 6


class HybridResult(BaseModel):
    id: str
    dense: float | None = None
    sparse: float | None = None
    in_graph: bool = False
    text: str | None = None
    component: str | None = None
    severity: float | None = None
    rrf: float = 0.0
    arms: list[str] = []


class HybridSearchResponse(BaseModel):
    query: str
    top_component: str | None = None
    counts: dict[str, int]
    results: list[HybridResult]


@router.post("/hybrid", response_model=HybridSearchResponse)
def hybrid(req: HybridSearchRequest) -> dict:
    return hybrid_search(req.query, k=req.k)
