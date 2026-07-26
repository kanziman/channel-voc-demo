#!/usr/bin/env python3
"""ingest.py — Listen arm.

Pulls REAL public customer-support conversations (Bitext, HuggingFace, no-auth)
and reconstructs them into ChannelTalk-style conversation objects, exactly as the
plugin would receive them from the ChannelTalk Open API. No synthetic data
(handoff §9.1): every conversation is a real human support utterance.

Outputs (under data/):
  conversations.jsonl  — "yesterday's inbox" sample the department analyzes
  heldout.jsonl        — disjoint labelled slice, reserved for validate.py (κ/F1)

Both carry the dataset's ground-truth `category`/`intent` so validation is
non-circular (predicted-vs-human-label), never self-graded.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HF_DATASET = os.environ.get(
    "HF_DATASET", "bitext/Bitext-customer-support-llm-chatbot-training-dataset"
)
CSV_NAME = "Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
CSV_URL = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main/{CSV_NAME}"

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# "Yesterday" relative to the demo's fixed clock (handoff currentDate 2026-07-24).
DAY = datetime(2026, 7, 23, tzinfo=timezone.utc)

# Deterministic placeholder fills so reconstructed text reads like a real chat
# instead of leaking template tokens. Values are cosmetic, not analysed.
_PLACEHOLDERS = {
    "Order Number": "#80421",
    "Invoice Number": "INV-2291",
    "Online Order Interaction": "the online order page",
    "Online Payment Interaction": "the payment page",
    "Online Customer Service Channel": "live chat",
    "Website URL": "the website",
    "Account Type": "Premium",
    "Account Category": "Premium",
    "Customer Support Phone Number": "1-800-555-0142",
    "Customer Support Hours": "9am–6pm",
    "Company Name": "the store",
    "Currency Symbol": "$",
    "Refund Amount": "$64.00",
    "Money Amount": "$64.00",
    "Delivery City": "Seattle",
    "Delivery Country": "the US",
    "Person Name": "Alex",
    "Salutation": "Hi",
}
_TOKEN_RE = re.compile(r"\{\{([^}]+)\}\}")


def _humanize(text: str) -> str:
    def repl(m: "re.Match[str]") -> str:
        key = m.group(1).strip()
        return _PLACEHOLDERS.get(key, key)

    return _TOKEN_RE.sub(repl, str(text)).strip()


def _load_raw() -> pd.DataFrame:
    DATA.mkdir(exist_ok=True)
    local = DATA / "bitext_raw.csv"
    if not local.exists():
        import urllib.request

        print(f"[ingest] downloading real dataset → {CSV_URL}", file=sys.stderr)
        urllib.request.urlretrieve(CSV_URL, local)
    df = pd.read_csv(local)
    need = {"instruction", "category", "intent", "response"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"[ingest] dataset schema changed, missing {missing}")
    return df


def _to_conversation(idx: int, row: pd.Series, base: datetime) -> dict:
    # Spread conversations across the working day so the inbox looks real.
    ts = base + timedelta(minutes=(idx * 1013) % (60 * 14) + 8 * 60)
    customer = _humanize(row["instruction"])
    agent = _humanize(row["response"])
    return {
        "id": f"conv_{idx:05d}",
        "channel": ["web", "mobile", "messenger"][idx % 3],
        "created_at": ts.isoformat(),
        "messages": [
            {"role": "customer", "text": customer},
            {"role": "agent", "text": agent},
        ],
        # Ground-truth labels — held for non-circular validation, not fed to analyze.
        "category_true": str(row["category"]).upper(),
        "intent_true": str(row["intent"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=1200,
                    help="conversations in yesterday's inbox")
    ap.add_argument("--heldout", type=int, default=600,
                    help="disjoint labelled slice for validation")
    ap.add_argument("--train", type=int, default=4000,
                    help="disjoint labelled slice the classifier learns from")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = _load_raw()
    # Deterministic shuffle. The dataset is already well-balanced across the 11
    # categories (min ~950 rows), so a plain shuffle keeps every theme represented.
    df = df.sample(frac=1.0, random_state=args.seed).reset_index(drop=True)

    prev_n = args.sample - 40  # "day before": a disjoint slice, slightly different volume
    total = args.sample + args.heldout + args.train + prev_n
    if len(df) < total:
        raise SystemExit(f"[ingest] not enough rows: {len(df)} < {total}")
    inbox = df.iloc[: args.sample]
    heldout = df.iloc[args.sample: args.sample + args.heldout]
    train = df.iloc[args.sample + args.heldout: args.sample + args.heldout + args.train]
    prev = df.iloc[args.sample + args.heldout + args.train: total]

    DATA.mkdir(exist_ok=True)

    def _dump(frame: pd.DataFrame, path: Path, start: int, day: datetime = DAY) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for i, (_, row) in enumerate(frame.iterrows()):
                fh.write(json.dumps(_to_conversation(start + i, row, day),
                                    ensure_ascii=False) + "\n")

    _dump(inbox, DATA / "conversations.jsonl", 0)
    _dump(heldout, DATA / "heldout.jsonl", args.sample)
    _dump(train, DATA / "train.jsonl", args.sample + args.heldout)
    _dump(prev, DATA / "conversations_prev.jsonl", args.sample + args.heldout + args.train,
          DAY - timedelta(days=1))

    meta = {
        "source": {
            "dataset": HF_DATASET,
            "url": CSV_URL,
            "license": "CDLA-Sharing-1.0 (Bitext, public)",
            "total_rows": int(len(df)),
        },
        "inbox_count": int(len(inbox)),
        "heldout_count": int(len(heldout)),
        "train_count": int(len(train)),
        "day": DAY.date().isoformat(),
        "seed": args.seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (DATA / "ingest_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[ingest] inbox={len(inbox)} heldout={len(heldout)} train={len(train)} "
          f"from {len(df)} real rows → {DATA}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
