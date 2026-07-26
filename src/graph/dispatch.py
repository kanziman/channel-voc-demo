"""Graph-native dispatcher (§2.3) — real GitHub issue + provenance edges.

On approval, creates a real GitHub Issue via `gh`, then records it in Neo4j as
an :Action with full provenance:
  (RootCause)-[:DISPATCHED_AS]->(Action)-[:EVIDENCES]->(Conversation)
so every shipped issue traces back to the exact conversations that justified it.

Idempotent: an open issue with the same title is reused, not duplicated —
demos re-run without spamming the repo.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

from . import config, db

REPO = os.getenv("GITHUB_TEST_REPO", "kanziman/channel-voc-demo")

_WRITE_ACTION = """
MERGE (a:Action {key: $key})
  SET a.type = 'github_issue', a.title = $title,
      a.url = coalesce($url, a.url),
      a.status = CASE WHEN a.status = 'dispatched' THEN 'dispatched' ELSE $status END,
      a.revenue_at_risk_krw = $revenue_at_risk_krw
WITH a
MATCH (r:RootCause {key: $root_cause_key})
MERGE (r)-[:DISPATCHED_AS]->(a)
WITH a
UNWIND $cited AS cid
  MATCH (c:Conversation {id: cid})
  MERGE (a)-[:EVIDENCES]->(c)
"""


def _gh(*args: str, check: bool = True) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return (r.stdout or "").strip()


def _existing_issue_url(title: str) -> str | None:
    try:
        out = _gh("issue", "list", "--repo", REPO, "--state", "all",
                  "--search", title, "--json", "title,url", check=False)
        for it in json.loads(out or "[]"):
            if it.get("title") == title:
                return it.get("url")
    except Exception:
        pass
    return None


def dispatch_issue(draft: dict, live: bool = False) -> dict:
    """Create (or reuse) a GitHub issue for a draft; record :Action in graph."""
    title = f"[VOC] {draft['title']}"
    action = {
        "key": f"act_{draft['root_cause_key']}",
        "root_cause_key": draft["root_cause_key"],
        "title": title,
        "url": None,
        "status": "drafted",
        "revenue_at_risk_krw": draft["revenue_at_risk_krw"],
        "cited": draft.get("cited_conv_ids", []),
    }

    if live:
        url = _existing_issue_url(title)
        if url:
            action.update(url=url, status="exists")
        else:
            with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
                f.write(draft["body"])
                body_file = f.name
            args = ["issue", "create", "--repo", REPO, "--title", title, "--body-file", body_file]
            out = _gh(*args, "--label", ",".join(draft.get("labels", []) or ["bug"]), check=False)
            if not out.startswith("http"):  # labels may not exist → retry bare
                out = _gh(*args)
            action.update(url=out.splitlines()[-1], status="dispatched")

    # Record provenance regardless (drafted/dispatched) so the graph is complete.
    db.run_write(
        _WRITE_ACTION,
        key=action["key"],
        title=title,
        url=action["url"],
        status=action["status"],
        revenue_at_risk_krw=action["revenue_at_risk_krw"],
        root_cause_key=action["root_cause_key"],
        cited=action["cited"],
    )
    return action


def main() -> int:
    """Dispatch the top drafted issue live (gate check for §2.3)."""
    import argparse

    from .drafter import draft_for_rootcause

    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="create a real GitHub issue")
    args = ap.parse_args()

    rcs = json.loads((config.OUT_DIR / "root_causes.json").read_text())
    draft = draft_for_rootcause(rcs[0])
    action = dispatch_issue(draft, live=args.live)
    print(f"Action: {action['status']}  {action['url'] or '(no url — not live)'}")
    print(f"  provenance edges → {len(action['cited'])} conversations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
