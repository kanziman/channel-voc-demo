---
name: channeltalk-solver
description: Channel VOC Intelligence Dept. — reads an entire day of ChannelTalk conversations, quantifies revenue-at-risk in ₩ with a validated model, and dispatches real GitHub Issues/PRs and Jira tickets. One invocation returns both a visual HTML dashboard (for people) and a structured manifest (for agents).
---

# Channel VOC Intelligence Dept. ("Insight that ships")

An always-on AI **department** — not a chatbot. The host agent (Codex / Claude)
invokes it once and it runs a full analyst shift over real customer conversations:

```text
Listen → Understand → Quantify (writes & runs code) → Validate → Dispatch (real actions) → Report
```

The differentiator is **execution**: it doesn't just summarize conversations, it
writes the analysis code, proves the theming against held-out human labels, and
creates **real** engineering, help-center, and CSM artifacts.

## When to use
Trigger on: "analyze yesterday's ChannelTalk conversations", "what should we fix
this week", "turn our support inbox into actions", "VOC report", "채널톡 대화 분석".

## Entry point — one command

```bash
python src/pipeline/run.py --execute      # full shift + real dispatch
python src/pipeline/run.py                 # analysis + dashboard, dispatch gated (dry-run)
python src/pipeline/run.py --no-dispatch   # analysis + dashboard only
```

`run.py` chains the five arms in order and writes two returns (see Dual Return).
Requirements: `python`, `pip install pandas scikit-learn` (see repo `.venv`), and
`GITHUB_TEST_REPO` in `.env`. GitHub auth via the `gh` CLI.

## The department (module = employee role)

| Arm | Script | Does |
| :-- | :-- | :-- |
| **Listen** | `src/pipeline/ingest.py` | Pulls real public CS conversations (Bitext, HuggingFace, no-auth) into ChannelTalk conversation format; reserves a held-out labelled slice. |
| **Analyst** | `src/pipeline/analyze.py` + `assumptions.py` | Trains a classifier on a disjoint slice, themes the inbox, scores sentiment/urgency, and quantifies **₩ revenue-at-risk** with a transparent, sourced model. Emits an audit trail (real conv ids + quotes) behind every number. |
| **Triage/QA** | `src/pipeline/validate.py` + `dispatch.py` | Validates theming on held-out human labels (Cohen's κ, macro-F1); files a real **GitHub Issue** for the top engineering cluster. |
| **Growth Ops** | `dispatch.py` | Opens a real **GitHub Pull Request** editing the live FAQ for the top help-center cluster. |
| **CSM Ops** | `dispatch.py` + host-agent MCP | Writes a save-play brief and files a real **Jira** ticket via the Atlassian MCP. |
| **Chief of Staff** | `src/pipeline/dashboard.py` + `run.py` | Renders the HTML dashboard and assembles the manifest. |

## Dual Return (the key contract)

One invocation returns two layers so both a human and an agent get "wow":

**Human layer** → `out/dashboard.html` — a self-contained, theme-aware console:
Exec KPI strip · Customer Truth Map (₩-ranked, click to trace to conversations) ·
Insight→Artifact flip cards linking the real Issue/PR/Jira · validation badges ·
auditable assumptions.

**Agent layer** → `out/manifest.json` — chainable structure:

```json
{
  "schema": "voc-intelligence.manifest/1",
  "briefing": "Read 1,200 real conversations … ₩20,630,500 at risk …",
  "dashboard_path": "out/dashboard.html",
  "metrics": { "conversations_read": 1200, "revenue_at_risk_krw": 20630500,
               "revenue_at_risk_band_pct": 2.8, "themes": 11,
               "cohen_kappa": 0.992, "macro_f1": 0.993,
               "intent_cohen_kappa": 0.971, "intent_macro_f1": 0.972,
               "actions_dispatched": 3 },
  "top_actions": [ { "theme": "ORDER", "arm": "triage", "revenue_at_risk_krw": 6484500,
                     "evidence": ["conv_00448", "…"] } ],
  "dispatched": [ { "type": "github_issue", "url": "https://github.com/…/issues/6", "via": "code: run.py --execute (gh CLI)" },
                  { "type": "github_pr",    "url": "https://github.com/…/pull/7",   "via": "code: run.py --execute (gh CLI)" },
                  { "type": "jira_issue",   "url": "https://…/browse/KAN-2",        "via": "agent+mcp: Atlassian Rovo MCP" } ],
  "validation": { "cohen_kappa": 0.992, "macro_f1": 0.993,
                  "intent_level": { "cohen_kappa": 0.971, "macro_f1": 0.972, "n_classes": 27 },
                  "caveat": "κ measures in-distribution theming separability (upper bound), not production noise.",
                  "method": "…held-out human labels…" },
  "source": { "dataset": "bitext/…", "license": "CDLA-Sharing-1.0" }
}
```

An agent can read `dispatched[].url` and keep going (comment, assign, notify);
a human opens `dashboard_path`.

## Integration surface (MCP / APIs)

- **GitHub** — real Issues + PRs via the `gh` CLI (`repo`, `workflow` scopes).
  Target repo from `GITHUB_TEST_REPO`. Maps 1:1 to ChannelTalk's "CX→Dev" loop.
- **Atlassian Rovo MCP** — real Jira issue via `createJiraIssue`
  (`write:jira-work`). The host agent performs this leg and writes
  `data/jira_dispatch.json`, which `run.py` folds into the manifest.
- **ChannelTalk Open API** (production surface, coded): `channeltalk_ingest.py`
  pulls real conversations from the **Open API v5** (`GET /open/v5/user-chats` +
  `/messages`, `x-access-key`/`x-access-secret`) into the identical
  `conversations.jsonl` schema — analyze/validate/dispatch/dashboard run unchanged.
  The demo uses the public labelled dataset because held-out validation needs human
  *labels* a live inbox lacks; the endpoint is verified reachable and swaps in with
  a workspace key.

## Safety
Auto-dispatch is gated: `DISPATCH_REQUIRE_APPROVAL=true` (default) means artifacts
are written to `data/artifacts/` for review and only pushed live with `--execute`.
`DISPATCH_CONFIDENCE_THRESHOLD` routes low-confidence themes to a review queue.

## Honesty
Conversation **counts and clusters are measured** from real data. The **₩
conversion is an explicit, sourced assumption model** (`assumptions.py`), surfaced
verbatim on the dashboard so a stakeholder can audit or override it. No synthetic
conversations are used.

## Reproduce the validation
```bash
python src/pipeline/ingest.py && python src/pipeline/analyze.py && python src/pipeline/validate.py
cat data/validation.json      # κ, macro-F1, per-class F1, confusion matrix
```
