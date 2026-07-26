"""LangGraph orchestration (§2.3) — the real agent, not a linear script.

StateGraph over a shared VOCState with:
  - a SQLite checkpointer (resume / reproducibility),
  - a conditional edge (drafts route to approval only if a gate demands it),
  - a real human-in-the-loop interrupt() at human_approval,
  - an activity log every node writes (powers the §2.4 Activity Feed visual).

Flow:
  analyst_extract → graph_writer → researcher_cluster → triage_rootcause
    → action_drafter → (needs approval?) → human_approval ─┐
                                     │ no                   │ approve
                                     ▼                      ▼
                                 dispatcher ────────────→ reporter

Run:
  python -m src.graph.agent                 # run to interrupt, auto-approve, dry dispatch
  python -m src.graph.agent --live          # actually create GitHub issues on approval
  python -m src.graph.agent --hold-first     # stop at the interrupt and print the gate
"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Annotated, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from . import config, db
from .drafter import draft_for_rootcause
from .extract import extract_many, load_conversations
from .rootcause import compute as compute_rootcauses

MAX_DRAFTS = int(os.getenv("VOC_MAX_DRAFTS", "3")) if (os := __import__("os")) else 3


def _log_reducer(existing: list, new: list) -> list:
    return (existing or []) + (new or [])


class VOCState(TypedDict, total=False):
    live: bool
    auto_approve: bool
    extracted: list[dict]
    graph_written: bool
    clusters: list[dict]
    root_causes: list[dict]
    candidate_actions: list[dict]
    approved_keys: list[str]
    dispatched: list[dict]
    briefing: str
    activity: Annotated[list[dict], _log_reducer]


def _act(node: str, message: str, t0: float, **extra) -> dict:
    return {"node": node, "message": message, "duration_s": round(time.time() - t0, 2),
            "ts": time.strftime("%H:%M:%S"), **extra}


# ── Nodes ────────────────────────────────────────────────────────────────────
def analyst_extract(state: VOCState) -> dict:
    t0 = time.time()
    convs = load_conversations()
    extractions = extract_many(convs, progress=False)
    return {
        "extracted": [{"n": len(extractions)}],
        "activity": [_act("analyst_extract",
                          f"대화 {len(extractions)}건에서 intent·증상·컴포넌트를 LLM으로 추출",
                          t0, count=len(extractions))],
    }


def graph_writer(state: VOCState) -> dict:
    t0 = time.time()
    counts = db.counts()
    if counts.get("Conversation", 0) >= 1000:
        msg = f"지식그래프 이미 적재됨 (대화 {counts.get('Conversation')}건) — 멱등 스킵"
    else:
        from .load import load as load_graph, _prepare
        rows = _prepare(extract_many(load_conversations(), progress=False))
        load_graph(rows)
        counts = db.counts()
        msg = f"지식그래프 MERGE 완료: {counts}"
    return {"graph_written": True,
            "activity": [_act("graph_writer", msg, t0, counts=counts)]}


def researcher_cluster(state: VOCState) -> dict:
    t0 = time.time()
    rows = db.run(
        "MATCH (conv:Conversation)-[:MENTIONS]->(:Symptom)-[:IMPLICATES]->(c:Component) "
        "RETURN c.name AS component, count(DISTINCT conv) AS n ORDER BY n DESC"
    )
    return {"clusters": rows,
            "activity": [_act("researcher_cluster",
                              f"대화를 {len(rows)}개 제품 컴포넌트로 클러스터링 (벡터 그래프)",
                              t0)]}


def triage_rootcause(state: VOCState) -> dict:
    t0 = time.time()
    rcs = compute_rootcauses()
    return {"root_causes": rcs,
            "activity": [_act("triage_rootcause",
                              f"그래프 순회 → 루트원인 {len(rcs)}건 승격 (라벨이 아닌 집계)",
                              t0, count=len(rcs))]}


def action_drafter(state: VOCState) -> dict:
    t0 = time.time()
    threshold = config.DISPATCH_CONFIDENCE_THRESHOLD
    candidates, held = [], []
    for rc in state["root_causes"][:MAX_DRAFTS]:
        draft = draft_for_rootcause(rc)
        draft["needs_approval"] = config.DISPATCH_REQUIRE_APPROVAL
        draft["auto_gate_pass"] = draft["confidence"] >= threshold
        candidates.append(draft)
    return {"candidate_actions": candidates,
            "activity": [_act("action_drafter",
                              f"GraphRAG로 이슈 {len(candidates)}건 초안 작성 (인용 conv_id, "
                              f"벡터+그래프 하이브리드 근거)",
                              t0, count=len(candidates))]}


def _needs_approval(state: VOCState) -> str:
    if state.get("auto_approve"):
        return "auto"
    if config.DISPATCH_REQUIRE_APPROVAL and state.get("candidate_actions"):
        return "human"
    return "auto"


def human_approval(state: VOCState) -> dict:
    """Real human-in-the-loop interrupt (§2.2). Pauses until a decision resumes it."""
    payload = {
        "message": "Approve which issues to dispatch? (reply with list of keys or 'all')",
        "candidates": [
            {"key": c["root_cause_key"], "title": c["title"], "severity": c["severity"],
             "revenue_at_risk_krw": c["revenue_at_risk_krw"], "confidence": c["confidence"],
             "cited": len(c["cited_conv_ids"])}
            for c in state["candidate_actions"]
        ],
    }
    decision = interrupt(payload)  # ← execution pauses here
    if decision in (None, "all"):
        approved = [c["root_cause_key"] for c in state["candidate_actions"]]
    elif isinstance(decision, list):
        approved = decision
    else:
        approved = [decision]
    return {"approved_keys": approved,
            "activity": [_act("human_approval", f"사람이 이슈 {len(approved)}건 승인: {approved}", time.time())]}


def _auto_approve(state: VOCState) -> dict:
    approved = [c["root_cause_key"] for c in state["candidate_actions"]
                if c.get("auto_gate_pass")]
    return {"approved_keys": approved,
            "activity": [_act("auto_approve",
                              f"신뢰도 게이트 통과 이슈 {len(approved)}건 자동 승인", time.time())]}


def dispatcher(state: VOCState) -> dict:
    t0 = time.time()
    from .dispatch import dispatch_issue
    approved = set(state.get("approved_keys") or [])
    out = []
    for c in state["candidate_actions"]:
        if c["root_cause_key"] in approved:
            out.append(dispatch_issue(c, live=state.get("live", False)))
    return {"dispatched": out,
            "activity": [_act("dispatcher",
                              f"이슈 {len(out)}건 배포 "
                              f"({'실제 → GitHub' if state.get('live') else '드라이런'}) + provenance 엣지 기록",
                              t0, count=len(out))]}


def reporter(state: VOCState) -> dict:
    t0 = time.time()
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "extracted": state.get("extracted"),
        "components": state.get("clusters"),
        "root_causes": [
            {k: rc[k] for k in ("key", "component", "frequency", "revenue_at_risk_krw",
                                "projected_recoverable_krw", "hypothesis", "sample_conv_ids")}
            for rc in state.get("root_causes", [])
        ],
        "candidate_actions": [
            {k: c[k] for k in ("root_cause_key", "component", "title", "labels", "severity",
                               "revenue_at_risk_krw", "confidence", "cited_conv_ids")}
            for c in state.get("candidate_actions", [])
        ],
        "dispatched": state.get("dispatched"),
        "activity": state.get("activity"),
    }
    total_risk = sum(rc["revenue_at_risk_krw"] for rc in state.get("root_causes", []))
    briefing = (
        f"VOC 인텔리전스 실행: 루트원인 {len(state.get('root_causes', []))}건, "
        f"매출 위험액 ₩{total_risk:,}, 이슈 {len(state.get('dispatched', []))}건 배포."
    )
    # Include reporter's own row so the manifest activity feed is the complete 8-step story.
    self_row = _act("reporter", "manifest.json + 브리핑 작성", t0)
    manifest["activity"] = (manifest.get("activity") or []) + [self_row]
    manifest["briefing"] = briefing
    out = config.OUT_DIR / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    # Full drafts (with hybrid evidence) for the dashboard's provenance cards.
    (config.OUT_DIR / "drafts.json").write_text(
        json.dumps(state.get("candidate_actions", []), ensure_ascii=False, indent=2)
    )
    return {"briefing": briefing,
            "activity": [_act("reporter", f"wrote manifest.json + briefing → {out}", t0)]}


# ── Graph assembly ───────────────────────────────────────────────────────────
def build_graph(checkpointer):
    g = StateGraph(VOCState)
    g.add_node("analyst_extract", analyst_extract)
    g.add_node("graph_writer", graph_writer)
    g.add_node("researcher_cluster", researcher_cluster)
    g.add_node("triage_rootcause", triage_rootcause)
    g.add_node("action_drafter", action_drafter)
    g.add_node("human_approval", human_approval)
    g.add_node("auto_approve", _auto_approve)
    g.add_node("dispatcher", dispatcher)
    g.add_node("reporter", reporter)

    g.add_edge(START, "analyst_extract")
    g.add_edge("analyst_extract", "graph_writer")
    g.add_edge("graph_writer", "researcher_cluster")
    g.add_edge("researcher_cluster", "triage_rootcause")
    g.add_edge("triage_rootcause", "action_drafter")
    g.add_conditional_edges("action_drafter", _needs_approval,
                            {"human": "human_approval", "auto": "auto_approve"})
    g.add_edge("human_approval", "dispatcher")
    g.add_edge("auto_approve", "dispatcher")
    g.add_edge("dispatcher", "reporter")
    g.add_edge("reporter", END)
    return g.compile(checkpointer=checkpointer)


def run(live: bool = False, auto_approve: bool = False, thread_id: str | None = None) -> dict:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    thread_id = thread_id or f"run-{int(time.time())}"
    cfg = {"configurable": {"thread_id": thread_id}}

    with SqliteSaver.from_conn_string(str(config.CACHE_DIR / "checkpoints.sqlite")) as cp:
        app = build_graph(cp)
        init: VOCState = {"live": live, "auto_approve": auto_approve}

        print("▶ running VOC Intelligence agent...\n")
        result = app.invoke(init, cfg)

        # If the graph interrupted for human approval, decide + resume.
        if "__interrupt__" in result:
            intr = result["__interrupt__"][0]
            payload = intr.value
            print("⏸  INTERRUPT — human approval gate reached:")
            for c in payload["candidates"]:
                print(f"    • {c['key']}  {c['title'][:60]}  "
                      f"[{c['severity']}] ₩{c['revenue_at_risk_krw']:,} conf={c['confidence']} cites={c['cited']}")
            # Approve those above the confidence gate (documented, deterministic).
            approve = [c["key"] for c in payload["candidates"]
                       if c["confidence"] >= config.DISPATCH_CONFIDENCE_THRESHOLD] or "all"
            print(f"\n▶ resuming with approval decision: {approve}\n")
            result = app.invoke(Command(resume=approve), cfg)

    _print_activity(result.get("activity", []))
    print(f"\n✅ {result.get('briefing')}")
    disp = result.get("dispatched") or []
    for d in disp:
        print(f"   → {d['status']}: {d.get('url') or '(dry-run, no url)'}  [{len(d.get('cited', []))} evidence convs]")
    return result


def _print_activity(activity: list[dict]) -> None:
    print("── Agent activity feed ─────────────────────────────")
    for a in activity:
        print(f"  [{a['ts']}] {a['node']:<18} {a['message']}  ({a['duration_s']}s)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="create real GitHub issues on approval")
    ap.add_argument("--auto", action="store_true", help="skip interrupt, auto-approve by gate")
    args = ap.parse_args()
    run(live=args.live, auto_approve=args.auto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
