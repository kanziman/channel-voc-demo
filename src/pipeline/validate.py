#!/usr/bin/env python3
"""validate.py — non-circular quality gate (handoff §7③).

Runs the trained classifier on the held-out slice — real conversations whose
human labels the model never saw — and reports agreement with those labels:
Cohen's κ, macro-F1, accuracy, and a confusion matrix. This is the honest
answer to "how good is the theming?" and is surfaced on the dashboard so a
stakeholder trusts the ₩ numbers that sit on top of it.

Inputs  : data/model.joblib, data/heldout.jsonl
Outputs : data/validation.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.metrics import (accuracy_score, classification_report,
                             cohen_kappa_score, confusion_matrix, f1_score)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _customer_text(conv: dict) -> str:
    return " ".join(m["text"] for m in conv["messages"] if m["role"] == "customer")


def _kappa_band(k: float) -> str:
    # Landis & Koch (1977) interpretation bands.
    if k >= 0.81:
        return "almost perfect"
    if k >= 0.61:
        return "substantial"
    if k >= 0.41:
        return "moderate"
    if k >= 0.21:
        return "fair"
    return "slight"


def _eval(model, held, target):
    X = [_customer_text(c) for c in held]
    y_true = [c[target] for c in held]
    y_pred = list(model.predict(X))
    labels = sorted(set(y_true) | set(y_pred))
    return {
        "cohen_kappa": round(float(cohen_kappa_score(y_true, y_pred)), 3),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro",
                                         labels=labels, zero_division=0)), 3),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 3),
        "n_classes": len(labels),
        "labels": labels,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "per_class_f1": {k: round(v["f1-score"], 3)
                         for k, v in classification_report(
                             y_true, y_pred, labels=labels, zero_division=0,
                             output_dict=True).items() if k in labels},
    }


def main() -> int:
    model = joblib.load(DATA / "model.joblib")
    held = [json.loads(l) for l in (DATA / "heldout.jsonl").open(encoding="utf-8") if l.strip()]

    cat = _eval(model, held, "category_true")
    # Intent theming is the harder, more realistic task (27 classes, fine-grained).
    intent = None
    ipath = DATA / "intent_model.joblib"
    if ipath.exists():
        intent = _eval(joblib.load(ipath), held, "intent_true")

    kappa = cat["cohen_kappa"]
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "heldout_count": len(held),
        "method": "TF-IDF(1,2-gram) + balanced LogisticRegression, trained on a "
                  "disjoint labelled slice; evaluated on unseen human labels.",
        "caveat": "κ/F1 measure how cleanly conversations separate into the dataset's "
                  "own theme labels (in-distribution). They quantify theming "
                  "reliability, not real-world label noise; production text is messier, "
                  "so treat these as an upper bound. The 27-class intent task below is "
                  "the harder, more realistic signal.",
        # Headline (category-level) — kept flat for back-compat with dashboard/manifest.
        "cohen_kappa": kappa,
        "kappa_band": _kappa_band(kappa),
        "macro_f1": cat["macro_f1"],
        "accuracy": cat["accuracy"],
        "labels": cat["labels"],
        "confusion_matrix": cat["confusion_matrix"],
        "per_class_f1": cat["per_class_f1"],
        "category_level": cat,
        "intent_level": intent,
    }
    (DATA / "validation.json").write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    itxt = (f" | intent κ={intent['cohen_kappa']} F1={intent['macro_f1']} "
            f"({intent['n_classes']} classes)") if intent else ""
    print(f"[validate] category n={len(held)} κ={kappa:.3f} ({out['kappa_band']}) "
          f"macroF1={cat['macro_f1']:.3f}{itxt}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
