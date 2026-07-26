#!/usr/bin/env python3
"""channeltalk_ingest.py — production Listen arm against the real ChannelTalk Open API.

Drop-in replacement for ingest.py's data source: instead of the public dataset,
it pulls real conversations from a ChannelTalk workspace via the Open API v5 and
writes the SAME `data/conversations.jsonl` schema, so analyze/validate/dispatch/
dashboard run unchanged.

Auth: CHANNEL_ACCESS_KEY / CHANNEL_ACCESS_SECRET (x-access-key / x-access-secret
headers). Endpoint: GET https://api.channel.io/open/v5/user-chats + messages.

The hackathon demo runs on the public Bitext dataset (see ingest.py) because
validation needs held-out human *labels*, which a live inbox doesn't carry. This
script is the real integration surface: point it at a seeded test workspace and
the rest of the department is identical. On a 401 it exits cleanly and tells you
to use ingest.py — it never fabricates conversations.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BASE = os.environ.get("CHANNEL_API_BASE", "https://api.channel.io")

def load_dotenv():
    env_file = ROOT / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_dotenv()

def _get(path: str) -> dict:
    key = os.environ.get("CHANNEL_ACCESS_KEY")
    secret = os.environ.get("CHANNEL_ACCESS_SECRET")
    if not key or not secret:
        raise SystemExit("[channeltalk] set CHANNEL_ACCESS_KEY / CHANNEL_ACCESS_SECRET, "
                         "or use ingest.py for the public-dataset demo.")
    req = urllib.request.Request(BASE.rstrip("/") + path,
                                 headers={"x-access-key": key, "x-access-secret": secret})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SystemExit("[channeltalk] 401 unauthenticated — the test-workspace key is "
                             "inactive. The endpoint is reachable; re-issue a key or run "
                             "ingest.py (public dataset) for the demo.")
        raise SystemExit(f"[channeltalk] HTTP {e.code}: {e.read().decode()[:200]}")


def _to_conversation(idx: int, chat: dict, messages: list[dict]) -> dict:
    msgs = []
    for m in messages:
        plain = (m.get("plainText") or m.get("message") or "").strip()
        if not plain:
            continue
        # personType: "user" = customer; "manager"/"bot" = agent.
        role = "customer" if m.get("personType") == "user" else "agent"
        msgs.append({"role": role, "text": plain})
    created = chat.get("createdAt") or 0
    ts = datetime.fromtimestamp(created / 1000, tz=timezone.utc) if created else datetime.now(timezone.utc)
    return {
        "id": chat.get("id", f"chat_{idx:05d}"),
        "channel": chat.get("source", {}).get("channel", "web") if isinstance(chat.get("source"), dict) else "web",
        "created_at": ts.isoformat(),
        "messages": msgs,
        # Live inboxes have no ground-truth theme labels; validation stays on the
        # labelled public slice. Tags, if present, are surfaced but not trusted as labels.
        "category_true": None,
        "intent_true": None,
        "channeltalk_tags": chat.get("tags", []),
    }


def main() -> int:
    limit = int(os.environ.get("CHANNEL_LIMIT", "200"))
    out, cursor, idx = [], None, 0
    while len(out) < limit:
        q = f"/open/v5/user-chats?state=closed&limit=25&sortOrder=desc"
        if cursor:
            q += f"&since={cursor}"
        page = _get(q)
        chats = page.get("userChats", []) or page.get("results", [])
        if not chats:
            break
        for chat in chats:
            msgs = _get(f"/open/v5/user-chats/{chat['id']}/messages?limit=50").get("messages", [])
            out.append(_to_conversation(idx, chat, msgs))
            idx += 1
            if len(out) >= limit:
                break
        cursor = page.get("next") or page.get("paging", {}).get("next")
        if not cursor:
            break

    DATA.mkdir(exist_ok=True)
    with (DATA / "conversations.jsonl").open("w", encoding="utf-8") as fh:
        for c in out:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"[channeltalk] pulled {len(out)} real conversations from the Open API → "
          f"data/conversations.jsonl", file=sys.stderr)
    print("[channeltalk] note: analyze.py needs a labelled slice for validation; keep "
          "data/{heldout,train}.jsonl from ingest.py or seed labels.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
