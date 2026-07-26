#!/usr/bin/env python3
"""dispatch_jira.py — CSM Ops arm, reproducible Jira leg.

The Jira ticket is normally created by the host agent through the Atlassian Rovo
MCP (`createJiraIssue`) — that is how KAN-2 in this repo was filed, live. This
script makes that leg reproducible and auditable instead of hand-asserted:

  • If JIRA_BASE_URL + JIRA_EMAIL + JIRA_API_TOKEN are set, it creates the issue
    via the Jira Cloud REST API and writes data/jira_dispatch.json itself.
  • Otherwise it prints the exact `createJiraIssue` MCP payload the host agent
    should run, and (unless --print-only) records the intended dispatch so the
    manifest stays honest about which leg is code vs agent+MCP.

Inputs  : data/analysis.json
Outputs : data/jira_dispatch.json (when executed)  |  MCP payload on stdout
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _krw(n: int) -> str:
    return f"₩{int(n):,}"


def _pick_csm_theme(analysis: dict) -> dict:
    return next(t for t in analysis["themes"] if t.get("arm") == "csm")


def _build(analysis: dict, theme: dict) -> tuple[str, str]:
    ev = "\n".join(f'- {r["conv_id"]} ({r.get("intent_pred") or r.get("intent_true")}): '
                   f'"{r["quote"]}"' for r in theme["representatives"])
    summary = (f"[VOC] {theme['theme']} save-play — {theme['count']} convs, "
               f"{_krw(theme['revenue_at_risk_krw'])} at risk")
    desc = (f"Auto-synthesized by Channel VOC Intelligence Dept. (CSM/Growth-Ops arm) "
            f"from real public CS conversations, analysis day {analysis['day']}.\n\n"
            f"## Situation\n{theme['count']} conversations ({theme['pct']}% of inbox) show "
            f"{theme['theme'].lower()} intent. Revenue at risk: {_krw(theme['revenue_at_risk_krw'])} "
            f"(intent-weighted assumption model). Mechanism: {theme['mechanism']}\n\n"
            f"## Recommended play\n1. Outreach to the accounts behind the highest-confidence "
            f"conversations.\n2. Lead with acknowledgement + concrete resolution.\n"
            f"3. Log outcome to measure saved revenue.\n\n## Evidence (real conversations)\n{ev}\n\n"
            f"_₩ basis (assumption): {theme['basis']}_")
    return summary, desc


def _rest_create(base: str, email: str, token: str, project: str,
                 summary: str, desc: str) -> str:
    payload = {
        "fields": {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": os.environ.get("JIRA_ISSUE_TYPE", "Task")},
            "description": {"type": "doc", "version": 1, "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": desc}]}]},
        }
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/rest/api/3/issue",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode(),
            "Content-Type": "application/json",
        }, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        key = json.load(r)["key"]
    return f"{base.rstrip('/')}/browse/{key}", key


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print-only", action="store_true",
                    help="only print the MCP payload; do not write jira_dispatch.json")
    ap.add_argument("--project", default=os.environ.get("JIRA_PROJECT_KEY", "KAN"))
    args = ap.parse_args()

    analysis = json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))
    theme = _pick_csm_theme(analysis)
    summary, desc = _build(analysis, theme)

    base = os.environ.get("JIRA_BASE_URL")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")

    if base and email and token:
        url, key = _rest_create(base, email, token, args.project, summary, desc)
        rec = {"type": "jira_issue", "theme": theme["theme"], "key": key, "title": summary,
               "url": url, "integration": "Jira Cloud REST API v3 (dispatch_jira.py)",
               "executed": True, "generated_at": datetime.now(timezone.utc).isoformat()}
        (DATA / "jira_dispatch.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False),
                                                 encoding="utf-8")
        print(f"[dispatch_jira] created {key} → {url}", file=sys.stderr)
        return 0

    # No REST creds → emit the exact MCP call for the host agent to run.
    mcp = {"tool": "createJiraIssue",
           "arguments": {"cloudId": os.environ.get("JIRA_CLOUD_ID", "<cloudId>"),
                         "projectKey": args.project, "issueTypeName": "Task",
                         "summary": summary, "contentFormat": "markdown", "description": desc}}
    print(json.dumps(mcp, indent=2, ensure_ascii=False))
    print("\n[dispatch_jira] no JIRA_* REST creds set — the host agent should run the "
          "createJiraIssue MCP call above, then write its result to data/jira_dispatch.json.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
