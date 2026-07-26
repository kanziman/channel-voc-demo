#!/usr/bin/env python3
"""dispatch.py — Triage/QA + Growth-Ops arms: turn insight into REAL artifacts.

Creates genuine GitHub artifacts in $GITHUB_TEST_REPO from the analysis:
  • a bug **Issue** for the top engineering (triage) cluster, and
  • a **Pull Request** that edits the live FAQ for the top help-center (faq) cluster.
Also writes a CSM briefing markdown for the top retention (csm) cluster (this file
is what the department hands to the CSM arm / a real Jira ticket).

Every artifact embeds its audit trail — the real conversation ids + verbatim
quotes it was synthesized from — so a reviewer can trace ₩ → ticket → conversation.

Safety: with --dry-run (or DISPATCH_REQUIRE_APPROVAL=true and no --execute) it
writes the artifact bodies to disk but performs no network mutation.

Inputs  : data/analysis.json
Outputs : data/dispatched.json, data/artifacts/*.md
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ART = DATA / "artifacts"
REPO = os.environ.get("GITHUB_TEST_REPO", "kanziman/channel-voc-demo")
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"$ {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return (r.stdout or "").strip()


def _krw(n: int) -> str:
    return f"₩{n:,}"


def _pick_theme(analysis: dict, arm: str) -> dict | None:
    """Highest-₩ theme owned by this arm (themes are pre-sorted by ₩ desc)."""
    return next((t for t in analysis["themes"] if t.get("arm") == arm), None)


def _evidence_block(theme: dict) -> str:
    lines = ["| conv id | intent (true) | verbatim customer quote |",
             "| --- | --- | --- |"]
    for r in theme["representatives"]:
        q = r["quote"].replace("|", "\\|")
        lines.append(f"| `{r['conv_id']}` | {r.get('intent_true','')} | {q} |")
    return "\n".join(lines)


def _signatures(theme: dict) -> str:
    """Suspected failure signatures = the predicted intents driving the cluster."""
    mix = theme.get("intent_mix") or []
    if not mix:
        return "- (intent breakdown unavailable)"
    return "\n".join(
        f'- `{m["intent"]}` — {m["count"]} conversations (risk weight {m["weight"]}×)'
        for m in mix)


def build_issue_body(analysis: dict, theme: dict) -> str:
    return f"""## 🐛 Auto-triaged from customer conversations — {theme['theme']} cluster

**Synthesized by:** Channel VOC Intelligence Dept. → Triage/QA arm
**Analysis day:** {analysis['day']}  |  **Source:** real public CS conversations ({analysis['source']['dataset']})

### Impact
- **{theme['count']}** conversations ({theme['pct']}% of yesterday's inbox) landed in this cluster.
- **Revenue at risk: {_krw(theme['revenue_at_risk_krw'])}** — each conversation priced by predicted intent (effective weight {theme['at_risk_rate']} × {_krw(theme['value_per_case_krw'])}/case).
- Mechanism: {theme['mechanism']}
- Severity: **{theme['severity']}** · avg negativity {theme['sentiment']}

### Suspected failure signatures (what's actually driving it)
{_signatures(theme)}

### Reproduction starting points (real customer utterances)
{_evidence_block(theme)}

### Suggested engineering action
1. Reproduce the top signature above (highest-weight intent) end-to-end in staging.
2. Confirm the order/checkout flow handles it; if it errors, this cluster is the bug's blast radius.
3. Link the reproducing conversations to the fix PR and close this issue.

> ₩ basis (assumption, auditable): {theme['basis']}

<sub>Generated automatically. Counts trace to the linked conversations; the ₩ conversion is a stated assumption, not a measured fact.</sub>
"""


def build_faq_patch(theme: dict) -> tuple[str, str]:
    """Return (section_markdown, pr_body)."""
    q_by_theme = {
        "DELIVERY": ("How long will delivery take, and why is my order still in transit?",
                     "Standard delivery is 2–5 business days. You can see live status "
                     "under **My Page → Orders → Track**. Cross-border orders may take longer "
                     "during customs clearance."),
        "SHIPPING": ("How much is shipping and can I change the shipping option?",
                     "Shipping cost is shown at checkout before payment. You can switch "
                     "between standard and express until the order is packed."),
        "ACCOUNT": ("I can't log in or register — what should I do?",
                    "Use **Forgot password** to reset, and make sure you register with the "
                    "same email used at checkout. Social logins are also supported."),
        "INVOICE": ("Where can I download my invoice?",
                    "Invoices are available under **My Page → Orders → Invoice** once the "
                    "order is paid."),
        "REFUND": ("How long does a refund take and how do I check its status?",
                   "Refunds are approved within 1 business day and returned to your original "
                   "payment method within a few business days. Track it under "
                   "**My Page → Orders → Refund status**."),
        "CONTACT": ("How do I reach a human agent?",
                    "Type **'agent'** in chat or use **Help → Talk to us** during support "
                    "hours (9am–6pm) to be routed to a person."),
    }
    q, a = q_by_theme.get(theme["theme"],
                          (f"Common question about {theme['theme'].lower()}",
                           "Please see the relevant section of your account."))
    section = f"\n**{q}**\n{a}\n"
    body = f"""## 📝 FAQ update proposed from recurring questions — {theme['theme']}

**Synthesized by:** Channel VOC Intelligence Dept. → Growth-Ops arm

This help-center clarification answers a cluster of **{theme['count']}** real customer
questions ({theme['pct']}% of yesterday's inbox), each currently handled one-by-one by
agents. Publishing it deflects the repeat load.

**Estimated exposure addressed:** {_krw(theme['revenue_at_risk_krw'])} (assumption model).

### Evidence (real conversations)
{_evidence_block(theme)}

<sub>Auto-generated FAQ diff. Review the wording before merge.</sub>
"""
    return section, body


def build_csm_brief(analysis: dict, theme: dict) -> str:
    return f"""# CSM Save-Play Brief — {theme['theme']} ({analysis['day']})

**From:** Channel VOC Intelligence Dept. → CSM/Growth-Ops arm

## Situation
{theme['count']} conversations ({theme['pct']}% of inbox) show **{theme['theme'].lower()}**
intent — a churn/retention signal. Revenue at risk: **{_krw(theme['revenue_at_risk_krw'])}**.
Mechanism: {theme['mechanism']}

## Recommended play
1. Prioritise outreach to the accounts behind the highest-confidence conversations below.
2. Lead with acknowledgement + a concrete resolution (not a discount).
3. Log outcome so the flywheel measures saved revenue.

## Evidence (real conversations)
{_evidence_block(theme)}

_₩ basis (assumption): {theme['basis']}_
"""


def _git(*a: str, cwd: Path) -> str:
    return _run(["git", "-c", "user.email=riserowner@gmail.com",
                 "-c", "user.name=kanziman", *a], cwd=cwd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="perform real GitHub mutations")
    ap.add_argument("--dry-run", action="store_true", help="write bodies only, no network")
    args = ap.parse_args()

    require_approval = os.environ.get("DISPATCH_REQUIRE_APPROVAL", "true").lower() == "true"
    execute = args.execute and not args.dry_run
    if require_approval and not args.execute:
        execute = False  # gate closed unless explicitly authorized

    analysis = json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))
    ART.mkdir(parents=True, exist_ok=True)
    threshold = float(os.environ.get("DISPATCH_CONFIDENCE_THRESHOLD", "0.7"))

    th_triage = _pick_theme(analysis, "triage")
    th_faq = _pick_theme(analysis, "faq")
    th_csm = _pick_theme(analysis, "csm")

    dispatched: list[dict] = []
    review_queue: list[dict] = []

    def _theme_conf(theme: dict) -> float:
        reps = theme.get("representatives") or []
        return sum(r["confidence"] for r in reps) / len(reps) if reps else 1.0

    def _gated(theme: dict) -> bool:
        """True = safe to dispatch; False = below confidence threshold, queued."""
        c = _theme_conf(theme)
        if c < threshold:
            review_queue.append({"theme": theme["theme"], "confidence": round(c, 3),
                                 "reason": f"mean theming confidence {c:.3f} < {threshold}"})
            return False
        return True

    # ---- 1. Bug Issue (triage) ------------------------------------------------
    if th_triage and _gated(th_triage):
        th = th_triage
        body = build_issue_body(analysis, th)
        (ART / "issue_body.md").write_text(body, encoding="utf-8")
        title = f"[VOC] {th['theme']} failure cluster — {th['count']} convs, {_krw(th['revenue_at_risk_krw'])} at risk"
        rec = {"type": "github_issue", "theme": th["theme"], "title": title,
               "body_file": "artifacts/issue_body.md", "executed": False, "url": None}
        if execute:
            url = _run(["gh", "issue", "create", "--repo", REPO, "--title", title,
                        "--body-file", str(ART / "issue_body.md"),
                        "--label", "bug"], check=False)
            if not url.startswith("http"):  # label may not exist; retry without it
                url = _run(["gh", "issue", "create", "--repo", REPO, "--title", title,
                            "--body-file", str(ART / "issue_body.md")])
            rec.update(executed=True, url=url.splitlines()[-1])
        dispatched.append(rec)

    # ---- 2. FAQ Pull Request (faq) -------------------------------------------
    if th_faq and _gated(th_faq):
        th = th_faq
        section, pr_body = build_faq_patch(th)
        (ART / "pr_body.md").write_text(pr_body, encoding="utf-8")
        (ART / "faq_section.md").write_text(section, encoding="utf-8")
        title = f"[VOC] FAQ: clarify {th['theme'].lower()} ({th['count']} recurring questions)"
        rec = {"type": "github_pr", "theme": th["theme"], "title": title,
               "body_file": "artifacts/pr_body.md", "executed": False, "url": None}
        if execute:
            repo_dir = DATA / "repo"
            if repo_dir.exists():
                import shutil
                shutil.rmtree(repo_dir)
            _run(["gh", "repo", "clone", REPO, str(repo_dir), "--", "-q"])
            branch = f"voc/faq-{th['theme'].lower()}-{STAMP}"
            _git("checkout", "-b", branch, cwd=repo_dir)
            faq = repo_dir / "docs" / "faq.md"
            faq.write_text(faq.read_text(encoding="utf-8").rstrip() + "\n" + section,
                           encoding="utf-8")
            _git("add", "-A", cwd=repo_dir)
            _git("commit", "-q", "-m",
                 f"FAQ: clarify {th['theme'].lower()} (auto from VOC analysis {analysis['day']})",
                 cwd=repo_dir)
            _git("push", "-q", "origin", branch, cwd=repo_dir)
            url = _run(["gh", "pr", "create", "--repo", REPO, "--head", branch,
                        "--title", title, "--body-file", str(ART / "pr_body.md")])
            rec.update(executed=True, url=url.splitlines()[-1], branch=branch)
        dispatched.append(rec)

    # ---- 3. CSM briefing (csm) — file artifact, feeds Jira/CRM ----------------
    if th_csm and _gated(th_csm):
        th = th_csm
        brief = build_csm_brief(analysis, th)
        (ART / "csm_brief.md").write_text(brief, encoding="utf-8")
        dispatched.append({"type": "csm_brief", "theme": th["theme"],
                           "body_file": "artifacts/csm_brief.md",
                           "title": f"CSM save-play — {th['theme']}",
                           "executed": True, "url": None,
                           "note": "Markdown brief ready for Jira/CRM hand-off (see dispatch_jira)."})

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": REPO,
        "executed": execute,
        "require_approval": require_approval,
        "confidence_threshold": threshold,
        "dispatched": dispatched,
        "review_queue": review_queue,
    }
    (DATA / "dispatched.json").write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    mode = "EXECUTED (real)" if execute else "DRY-RUN (bodies only)"
    print(f"[dispatch] {mode} → {len(dispatched)} artifacts, repo={REPO}", file=sys.stderr)
    for d in dispatched:
        print(f"           {d['type']:12} {d.get('url') or d['body_file']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
