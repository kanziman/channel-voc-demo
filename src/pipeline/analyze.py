#!/usr/bin/env python3
"""analyze.py — Analyst arm ("writes code to quantify Customer Truth").

Reads yesterday's real conversations, classifies each into a theme with a model
trained on a DISJOINT labelled slice (so nothing is self-graded), scores sentiment
and urgency, then quantifies revenue-at-risk per theme via the transparent model
in assumptions.py. Every ₩ figure carries an audit trail: the real conversation
ids and verbatim quotes it was computed from (handoff §7②).

Inputs  : data/train.jsonl, data/conversations.jsonl
Outputs : data/model.joblib, data/analysis.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

import assumptions as A

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Lightweight, dependency-free lexicons (no external API — fully reproducible).
_NEG = {"can't", "cannot", "won't", "not", "never", "unable", "fail", "failed",
        "error", "wrong", "broken", "issue", "problem", "refund", "cancel",
        "angry", "frustrated", "disappointed", "terrible", "worst", "bad",
        "charged", "double", "missing", "lost", "delay", "delayed", "late",
        "stuck", "still", "again", "complaint", "unacceptable"}
_URGENT = {"urgent", "asap", "immediately", "right now", "still not", "again",
           "already", "waiting", "days", "hours", "emergency", "now"}


def _load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def _customer_text(conv: dict) -> str:
    return " ".join(m["text"] for m in conv["messages"] if m["role"] == "customer")


def _score(text: str, lex: set[str]) -> int:
    toks = re.findall(r"[a-z']+", text.lower())
    uni = sum(1 for t in toks if t in lex)
    bi = sum(1 for p in (f"{a} {b}" for a, b in zip(toks, toks[1:])) if p in lex)
    return uni + bi


def _sentiment(text: str) -> float:
    """0..1 negativity — higher = angrier. Normalised by length."""
    n = _score(text, _NEG)
    words = max(len(text.split()), 1)
    return round(min(1.0, n / max(words * 0.12, 1)), 3)


def _urgency(text: str) -> float:
    u = _score(text, _URGENT)
    return round(min(1.0, u / 3.0), 3)


def train_model(train: list[dict], target: str) -> Pipeline:
    X = [_customer_text(c) for c in train]
    y = [c[target] for c in train]
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                  stop_words="english")),
        ("clf", LogisticRegression(max_iter=1000, C=4.0, class_weight="balanced")),
    ])
    pipe.fit(X, y)
    return pipe


def main() -> int:
    train = _load(DATA / "train.jsonl")
    inbox = _load(DATA / "conversations.jsonl")
    meta = json.loads((DATA / "ingest_meta.json").read_text())

    # Two classifiers: coarse theme (category) and fine intent. The intent model
    # lets us price each conversation by what it actually is, and gives a harder,
    # more credible validation task (27 classes vs 11).
    model = train_model(train, "category_true")
    intent_model = train_model(train, "intent_true")
    joblib.dump(model, DATA / "model.joblib")
    joblib.dump(intent_model, DATA / "intent_model.joblib")

    texts = [_customer_text(c) for c in inbox]
    pred = model.predict(texts)
    proba = model.predict_proba(texts)
    conf = proba.max(axis=1)
    pred_intent = list(intent_model.predict(texts))

    # Group predicted conversations into themes (= predicted category).
    buckets: dict[str, list[int]] = defaultdict(list)
    for i, cat in enumerate(pred):
        buckets[cat].append(i)

    # Which department arm owns each theme (dispatch routes on this).
    ARM = {"PAYMENT": "triage", "ORDER": "triage", "REFUND": "csm", "CANCEL": "csm",
           "SUBSCRIPTION": "csm", "DELIVERY": "faq", "SHIPPING": "faq",
           "INVOICE": "faq", "ACCOUNT": "faq", "CONTACT": "faq", "FEEDBACK": "csm"}

    themes = []
    for cat, idxs in buckets.items():
        count = len(idxs)
        sent = float(np.mean([_sentiment(texts[i]) for i in idxs]))
        urg = float(np.mean([_urgency(texts[i]) for i in idxs]))
        # Intent-aware ₩: price each conversation by its predicted intent, then sum.
        rar = int(round(sum(A.conversation_risk_krw(cat, pred_intent[i]) for i in idxs)))
        eff_rate = float(np.mean([A.intent_weight(pred_intent[i]) for i in idxs]))
        # Intent mix driving this theme (predicted), for transparency. Always
        # reconciles to the full theme count: a remainder bucket carries the rest
        # (with its true mean weight) so the effective ₩ rate is reconstructable.
        mix = Counter(pred_intent[i] for i in idxs)
        top = mix.most_common(4)
        intent_mix = [{"intent": k, "count": c, "weight": A.intent_weight(k)} for k, c in top]
        shown = sum(c for _, c in top)
        if shown < count:
            rest = [i for i in idxs if pred_intent[i] not in {k for k, _ in top}]
            rest_w = float(np.mean([A.intent_weight(pred_intent[i]) for i in rest]))
            intent_mix.append({"intent": f"other ({len(set(pred_intent[i] for i in rest))} intents)",
                               "count": count - shown, "weight": round(rest_w, 2)})
        # Representatives = highest-confidence, highest-negativity real conversations.
        ranked = sorted(idxs, key=lambda i: (conf[i], _sentiment(texts[i])), reverse=True)
        reps = []
        for i in ranked[:3]:
            q = _customer_text(inbox[i]).strip()
            reps.append({
                "conv_id": inbox[i]["id"],
                "confidence": round(float(conf[i]), 3),
                "intent_pred": pred_intent[i],
                "intent_weight": A.intent_weight(pred_intent[i]),
                "intent_true": inbox[i].get("intent_true"),
                "quote": (q[:220] + "…") if len(q) > 220 else q,
            })
        m = A.model_for(cat)
        themes.append({
            "theme": cat,
            "arm": ARM.get(cat, "faq"),
            "count": count,
            "pct": round(100 * count / len(inbox), 1),
            "sentiment": round(sent, 3),
            "urgency": round(urg, 3),
            "severity": m["severity"],
            "revenue_at_risk_krw": rar,
            "at_risk_rate": round(eff_rate, 3),          # effective, intent-weighted
            "value_per_case_krw": m["value_per_case_krw"],
            "intent_mix": intent_mix,
            "mechanism": m["mechanism"],
            "basis": m["basis"],
            "representatives": reps,
        })

    # Day-over-day trend: classify the prior-day slice with the same model and
    # compare per-theme prevalence, so a stakeholder sees what's structural vs new.
    prev_counts: dict = {}
    prev_path = DATA / "conversations_prev.jsonl"
    if prev_path.exists():
        prev = _load(prev_path)
        ptexts = [_customer_text(c) for c in prev]
        for cat in model.predict(ptexts):
            prev_counts[cat] = prev_counts.get(cat, 0) + 1
        prev_total = len(prev)
        for t in themes:
            today_share = t["count"] / len(inbox)
            prev_c = prev_counts.get(t["theme"], 0)
            prev_share = prev_c / prev_total if prev_total else 0
            delta_pp = round((today_share - prev_share) * 100, 1)
            t["trend"] = {"prev_count": prev_c,
                          "delta_conversations": t["count"] - prev_c,
                          "delta_share_pp": delta_pp,
                          "direction": "up" if delta_pp > 0.3 else ("down" if delta_pp < -0.3 else "flat")}

    themes.sort(key=lambda t: t["revenue_at_risk_krw"], reverse=True)
    total_rar = sum(t["revenue_at_risk_krw"] for t in themes)
    projected_recoverable = A.projected_recoverable_krw(total_rar)

    # Top actions: the highest-₩ themes become concrete dispatch recommendations.
    action_map = {
        "PAYMENT": ("triage", "Payment/checkout failure cluster → engineering bug ticket"),
        "ORDER": ("triage", "Order placement/tracking defects → engineering bug ticket"),
        "REFUND": ("csm", "Refund friction → CSM save-play + FAQ clarification"),
        "CANCEL": ("csm", "Cancellation intent spike → retention save-flow brief"),
        "SUBSCRIPTION": ("csm", "Subscription churn risk → CSM outreach brief"),
        "DELIVERY": ("faq", "Delivery-time confusion → FAQ update"),
        "SHIPPING": ("faq", "Shipping cost/options questions → FAQ update"),
        "INVOICE": ("faq", "Invoice/billing confusion → FAQ update"),
        "ACCOUNT": ("faq", "Login/registration friction → FAQ + self-serve fix"),
        "CONTACT": ("faq", "Agent-reachability complaints → routing/FAQ update"),
        "FEEDBACK": ("csm", "Aggregated feedback → product signal brief"),
    }
    top_actions = []
    for t in themes[:5]:
        arm, desc = action_map.get(t["theme"], ("faq", "Review cluster"))
        top_actions.append({
            "theme": t["theme"],
            "arm": arm,
            "description": desc,
            "count": t["count"],
            "revenue_at_risk_krw": t["revenue_at_risk_krw"],
            "severity": t["severity"],
            "evidence": [r["conv_id"] for r in t["representatives"]],
        })

    analysis = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "day": meta["day"],
        "source": meta["source"],
        "inbox_count": len(inbox),
        "theme_count": len(themes),
        "total_revenue_at_risk_krw": total_rar,
        "projected_recoverable_krw": projected_recoverable,
        "recovery_rate": A.RECOVERY_RATE,
        "has_trend": bool(prev_counts),
        "sentiment_avg": round(float(np.mean([_sentiment(t) for t in texts])), 3),
        "themes": themes,
        "top_actions": top_actions,
        "assumptions": A.assumptions_manifest(),
    }
    (DATA / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    print(f"[analyze] {len(inbox)} convs → {len(themes)} themes, "
          f"₩{total_rar:,} at risk (top: {themes[0]['theme']} ₩{themes[0]['revenue_at_risk_krw']:,})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
