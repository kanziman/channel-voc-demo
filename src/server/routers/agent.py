"""Agent API (§2.3, §5-3) [WRAP+신규설계].

Maps LangGraph's interrupt()/Command(resume) onto a *stateless* HTTP pair:

  POST /api/agent/run       → start the approval graph, persist the paused
                              checkpoint to Neo4j, return {thread_id, interrupt}.
  POST /api/agent/dispatch  → a SEPARATE request builds a fresh saver + graph
                              and resumes the same thread_id from Neo4j, so the
                              approval survives the process/request boundary
                              (the property #12's spike proved).

The heavy ingestion pipeline (extraction/graph load) is offline; this focused
graph only runs the human-in-the-loop approval → dispatch step over already
computed root causes, so a run/dispatch cycle is cheap and LLM-free.
"""
from __future__ import annotations

import uuid
from typing import TypedDict

from fastapi import APIRouter, HTTPException
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from ...graph.checkpoint_neo4j import Neo4jCheckpointSaver
from ...graph.dispatch import dispatch_issue
from ...graph.rootcause import compute as compute_rootcauses

router = APIRouter(prefix="/api/agent", tags=["agent"])

_CANDIDATE_KEYS = ("root_cause_key", "component", "title",
                   "revenue_at_risk_krw", "confidence", "cited_conv_ids")


def _candidates_from_rootcauses(rcs: list[dict]) -> list[dict]:
    return [{
        "root_cause_key": rc["key"],
        "component": rc["component"],
        "title": rc.get("hypothesis") or f"{rc['component']} root cause",
        "revenue_at_risk_krw": rc["revenue_at_risk_krw"],
        "confidence": rc.get("confidence_avg"),
        "cited_conv_ids": rc.get("sample_conv_ids", []),
    } for rc in rcs]


# ── focused approval graph (interrupt → dispatch) ─────────────────────────────
class _AgentState(TypedDict, total=False):
    candidates: list[dict]
    live: bool
    approved_keys: list[str]
    dispatched: list[dict]


def _approved_from_decision(decision, candidates: list[dict]) -> list[str]:
    all_keys = [c["root_cause_key"] for c in candidates]
    if decision in (None, "approve", "all"):
        return all_keys
    if decision in ("reject", "none", []):
        return []
    if isinstance(decision, list):
        return decision
    return [decision]


def _human_approval(state: _AgentState) -> dict:
    payload = {
        "message": "Approve which root-cause issues to dispatch?",
        "candidates": [{k: c.get(k) for k in _CANDIDATE_KEYS} for c in state["candidates"]],
    }
    decision = interrupt(payload)  # ← pauses here; persisted to Neo4j
    return {"approved_keys": _approved_from_decision(decision, state["candidates"])}


def _dispatcher(state: _AgentState) -> dict:
    approved = set(state.get("approved_keys") or [])
    out = [dispatch_issue(c, live=state.get("live", False))
           for c in state["candidates"] if c["root_cause_key"] in approved]
    return {"dispatched": out}


def build_approval_graph(checkpointer):
    g = StateGraph(_AgentState)
    g.add_node("human_approval", _human_approval)
    g.add_node("dispatcher", _dispatcher)
    g.add_edge(START, "human_approval")
    g.add_edge("human_approval", "dispatcher")
    g.add_edge("dispatcher", END)
    return g.compile(checkpointer=checkpointer)


# ── request/response models ───────────────────────────────────────────────────
class RunRequest(BaseModel):
    live: bool = False


class DispatchRequest(BaseModel):
    thread_id: str
    decision: str | list[str] = "approve"


# ── endpoints ─────────────────────────────────────────────────────────────────
@router.get("/rootcauses")
def rootcauses() -> dict:
    return {"rootcauses": compute_rootcauses(write=False)}


@router.post("/run")
def run(req: RunRequest) -> dict:
    Neo4jCheckpointSaver.setup()
    candidates = _candidates_from_rootcauses(compute_rootcauses(write=False))
    thread_id = f"agent-{uuid.uuid4().hex[:12]}"
    # nothing to approve → no interrupt, no checkpoint
    if not candidates:
        return {"thread_id": thread_id, "interrupt": None, "dispatched": []}
    app = build_approval_graph(Neo4jCheckpointSaver())
    cfg = {"configurable": {"thread_id": thread_id}}
    result = app.invoke({"candidates": candidates, "live": req.live}, cfg)
    return {"thread_id": thread_id, "interrupt": result["__interrupt__"][0].value,
            "dispatched": None}


@router.post("/dispatch")
def dispatch(req: DispatchRequest) -> dict:
    saver = Neo4jCheckpointSaver()  # fresh — stateless resume from Neo4j
    cfg: RunnableConfig = {"configurable": {"thread_id": req.thread_id}}
    if saver.get_tuple(cfg) is None:  # typo'd / expired thread_id — don't 500
        raise HTTPException(status_code=404, detail="unknown or expired thread_id")
    result = build_approval_graph(saver).invoke(Command(resume=req.decision), cfg)
    dispatched = result.get("dispatched", [])
    return {"thread_id": req.thread_id,
            "status": "dispatched" if dispatched else "rejected",
            "dispatched": dispatched}
