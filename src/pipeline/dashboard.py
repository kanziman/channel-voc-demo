#!/usr/bin/env python3
"""dashboard.py — Chief-of-Staff arm: the Human-layer deliverable.

Renders one self-contained, theme-aware HTML console from the real pipeline
outputs. No external requests (CSP-safe): all CSS/JS inline, system-font stack so
nothing silently falls back. Four decision surfaces:
  1. Exec strip  — the numbers a stakeholder decides on, summary before detail.
  2. Customer Truth Map — themes ranked by ₩ at risk, colour = severity,
     expandable to the real conversation quotes each figure traces to.
  3. Insight → Artifact — flip cards linking the *real* dispatched Issue/PR/Jira.
  4. Agent Activity — the department's run log.
Plus an auditable Assumptions panel and the held-out validation badges.

Inputs  : data/{analysis,validation,dispatched,ingest_meta}.json (+ jira_dispatch.json)
Output  : out/dashboard.html
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "out"

SEV_COLOR = {"high": "var(--sev-high)", "medium": "var(--sev-med)", "low": "var(--sev-low)"}


def _load(name: str, default=None):
    p = DATA / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def krw(n: int) -> str:
    return f"₩{int(n):,}"


def _fmt_ts(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%H:%M:%S UTC")
    except Exception:
        return iso


# ─────────────────────────────────────────────────────────── sections ──────
def exec_strip(a: dict, v: dict, disp: dict, jira: dict | None) -> str:
    n_dispatched = len([d for d in disp.get("dispatched", []) if d.get("executed")])
    n_dispatched += 1 if jira else 0
    top = a["themes"][0]
    intent = (v or {}).get("intent_level") or {}
    # Lead with the honest, harder signal (27-class intent), not the flattering
    # in-distribution 11-theme number — that sits in the subtitle.
    head_k = intent.get("cohen_kappa", v["cohen_kappa"]) if v else "—"
    sub_k = v["cohen_kappa"] if v else "—"
    cards = [
        ("Revenue at risk / day", krw(a["total_revenue_at_risk_krw"]), "accent",
         f"±{round((1-intent.get('macro_f1',1))*100,1)}% band · {a['theme_count']} themes" if intent
         else f"across {a['theme_count']} themes"),
        ("Conversations read", f"{a['inbox_count']:,}", "plain",
         f"day {a['day']} · 100% coverage"),
        ("Top exposure", f"{top['theme']}", "sev",
         f"{krw(top['revenue_at_risk_krw'])} · {top['count']} convs"),
        ("Projected recoverable", krw(a.get("projected_recoverable_krw", 0)), "good",
         f"if actioned · {int(a.get('recovery_rate',0)*100)}% recovery (assumption)"),
        ("Theming quality (held-out)", f"κ {head_k}", "good",
         f"27-class intent · 11-theme κ {sub_k} · {v['heldout_count'] if v else '—'} labels"),
        ("Real actions dispatched", f"{n_dispatched}", "accent",
         "Issue · PR · Jira — live"),
    ]
    out = ['<section class="strip" aria-label="Executive summary">']
    for label, big, tone, sub in cards:
        out.append(f'''<div class="kpi kpi--{tone}">
          <div class="kpi__label">{esc(label)}</div>
          <div class="kpi__value">{esc(big)}</div>
          <div class="kpi__sub">{esc(sub)}</div></div>''')
    out.append("</section>")
    return "\n".join(out)


def _trend_chip(t: dict) -> str:
    tr = t.get("trend")
    if not tr:
        return ""
    d = tr["delta_share_pp"]
    arrow = "▲" if tr["direction"] == "up" else ("▼" if tr["direction"] == "down" else "▪")
    cls = tr["direction"]
    sign = "+" if d > 0 else ""
    return (f'<span class="trend trend--{cls}" title="vs the prior day">'
            f'{arrow} {sign}{d}pp d/d</span>')


def _intent_mix(t: dict) -> str:
    mix = t.get("intent_mix") or []
    if not mix:
        return ""
    chips = "".join(
        f'<span class="ichip" title="risk weight {m["weight"]}×">{esc(m["intent"])}'
        f'<span class="ichip__n">{m["count"]}</span>'
        f'<span class="ichip__w ichip__w--{"info" if m["weight"]<0.5 else ("churn" if m["weight"]>1 else "fric")}">{m["weight"]}×</span></span>'
        for m in mix)
    return f'<div class="imix"><span class="imix__k">intent mix →</span>{chips}</div>'


def truth_map(a: dict) -> str:
    themes = a["themes"]
    maxrar = max(t["revenue_at_risk_krw"] for t in themes) or 1
    rows = []
    for t in themes:
        w = max(4, round(100 * t["revenue_at_risk_krw"] / maxrar))
        sent_pct = round(t["sentiment"] * 100)
        reps = "".join(
            f'''<li><span class="rep__meta"><code>{esc(r["conv_id"])}</code>
               <span class="rep__intent">{esc(r.get("intent_pred") or r.get("intent_true",""))}</span>
               <span class="rep__w">{r.get("intent_weight","")}×</span>
               <span class="rep__conf">conf {r["confidence"]}</span></span>
               <span class="rep__quote">“{esc(r["quote"])}”</span></li>'''
            for r in t["representatives"])
        rows.append(f'''
        <details class="theme" style="--bar:{w}%;--sev:{SEV_COLOR[t['severity']]}">
          <summary>
            <span class="theme__head">
              <span class="theme__name">{esc(t["theme"])}
                <span class="sev-pill sev-pill--{t['severity']}">{esc(t['severity'])}</span>
                <span class="arm-tag">{esc(t['arm'])}</span></span>
              <span class="theme__rar">{krw(t["revenue_at_risk_krw"])}</span>
            </span>
            <span class="theme__bar"><span class="theme__fill"></span></span>
            <span class="theme__meta">
              <span>{t["count"]} convs · {t["pct"]}%</span>
              {_trend_chip(t)}
              <span class="senti" title="avg negativity">
                <span class="senti__track"><span class="senti__fill" style="width:{sent_pct}%"></span></span>
                negativity {t["sentiment"]}</span>
              <span class="chev">view evidence ▾</span>
            </span>
          </summary>
          <div class="theme__body">
            <p class="theme__mech">{esc(t["mechanism"])}</p>
            <p class="theme__basis"><strong>₩ basis (assumption):</strong> {esc(t["basis"])}
               — each conversation priced by predicted intent (×{krw(t["value_per_case_krw"])}/case);
               effective at-risk weight {t["at_risk_rate"]} across {t["count"]} convs.</p>
            {_intent_mix(t)}
            <ul class="reps">{reps}</ul>
          </div>
        </details>''')
    return f'''<section class="panel" id="truthmap">
      <div class="panel__head"><h2>Customer Truth Map</h2>
        <p class="panel__sub">Every theme measured from real conversations, ranked by revenue at risk.
        Bar length = ₩ exposure · colour = severity. Expand any row to trace the ₩ back to the exact conversations.</p></div>
      <div class="themes">{''.join(rows)}</div>
    </section>'''


def _diff_snippet() -> str:
    faq = DATA / "artifacts" / "faq_section.md"
    if not faq.exists():
        return ""
    lines = [l for l in faq.read_text(encoding="utf-8").splitlines() if l.strip()]
    body = "\n".join(f'<span class="add">+ {esc(l)}</span>' for l in lines)
    return f'<pre class="diff">{body}</pre>'


def artifact_cards(disp: dict, jira: dict | None, a: dict) -> str:
    by_theme = {t["theme"]: t for t in a["themes"]}
    cards = []
    for d in disp.get("dispatched", []):
        theme = d.get("theme", "")
        t = by_theme.get(theme, {})
        rar = krw(t.get("revenue_at_risk_krw", 0)) if t else ""
        kind = d["type"]
        if kind == "github_issue":
            badge, cta, back = "GitHub Issue", "Open issue ↗", _diff_snippet()
            icon = "🐛"; extra = ""
        elif kind == "github_pr":
            badge, cta = "GitHub Pull Request", "Open PR ↗"
            icon = "🔀"; extra = _diff_snippet()
        else:
            badge, cta, extra, icon = "CSM Brief", "", "", "📋"
        url = d.get("url")
        via = "gh CLI · run.py --execute" if kind.startswith("github") else "file artifact"
        link = (f'<a class="artifact__cta" href="{esc(url)}" target="_blank" rel="noopener">{cta}</a>'
                if url else '<span class="artifact__cta artifact__cta--file">file artifact</span>')
        via_tag = f'<span class="viatag">via {esc(via)}</span>'
        cards.append(f'''
        <article class="flip" tabindex="0" aria-label="{esc(badge)} for {esc(theme)}">
          <div class="flip__inner">
            <div class="flip__face flip__front">
              <span class="artifact__badge">{icon} {esc(badge)}</span>
              <h3>{esc(theme)} cluster</h3>
              <p class="artifact__prob">{esc(t.get("mechanism",""))}</p>
              <div class="artifact__num"><span>{rar}</span><small>at risk</small></div>
              <span class="flip__hint">hover / focus to see the dispatched artifact →</span>
            </div>
            <div class="flip__face flip__back">
              <span class="artifact__badge">{icon} {esc(badge)}</span>
              <p class="artifact__title">{esc(d.get("title",""))}</p>
              {extra}
              {link}
              {via_tag}
            </div>
          </div>
        </article>''')
    if jira:
        cards.append(f'''
        <article class="flip" tabindex="0" aria-label="Jira issue for {esc(jira["theme"])}">
          <div class="flip__inner">
            <div class="flip__face flip__front">
              <span class="artifact__badge artifact__badge--jira">🧭 Jira (via MCP)</span>
              <h3>{esc(jira["theme"])} save-play</h3>
              <p class="artifact__prob">Retention/churn signal routed to the CSM board live over the Atlassian MCP.</p>
              <div class="artifact__num"><span>{esc(jira["key"])}</span><small>ticket</small></div>
              <span class="flip__hint">hover / focus to open →</span>
            </div>
            <div class="flip__face flip__back">
              <span class="artifact__badge artifact__badge--jira">🧭 {esc(jira["integration"])}</span>
              <p class="artifact__title">{esc(jira["title"])}</p>
              <a class="artifact__cta" href="{esc(jira["url"])}" target="_blank" rel="noopener">Open {esc(jira["key"])} ↗</a>
            </div>
          </div>
        </article>''')
    return f'''<section class="panel" id="artifacts">
      <div class="panel__head"><h2>Insight → Artifact</h2>
        <p class="panel__sub">The loop closes here. Each card's back is a <strong>real</strong> artifact this run dispatched —
        click through to the live Issue, Pull Request, and Jira ticket.</p></div>
      <div class="flips">{''.join(cards)}</div>
    </section>'''


def activity_feed(a: dict, v: dict, disp: dict, meta: dict, jira: dict | None) -> str:
    ev = []
    src = a["source"]
    ev.append(("Listen", meta["generated_at"],
               f'Ingested {meta["inbox_count"]:,} real conversations (+{meta["heldout_count"]} held-out) '
               f'from {esc(src["dataset"])}.'))
    ev.append(("Analyst", a["generated_at"],
               f'Wrote & ran classification + ₩ model → {a["theme_count"]} themes, '
               f'{krw(a["total_revenue_at_risk_krw"])} at risk.'))
    if v:
        ev.append(("Triage/QA", v["generated_at"],
                   f'Validated on held-out human labels: κ={v["cohen_kappa"]} '
                   f'({v["kappa_band"]}), macro-F1={v["macro_f1"]}.'))
    for d in disp.get("dispatched", []):
        if d.get("url"):
            ev.append(("Dispatch", disp["generated_at"],
                       f'{esc(d["type"].replace("_"," "))} created → '
                       f'<a href="{esc(d["url"])}" target="_blank" rel="noopener">{esc(d["url"])}</a>'))
        elif d["type"] == "csm_brief":
            ev.append(("CSM Ops", disp["generated_at"],
                       'Generated CSM save-play brief for hand-off.'))
    if jira:
        ev.append(("CSM Ops", a["generated_at"],
                   f'Dispatched <a href="{esc(jira["url"])}" target="_blank" rel="noopener">{esc(jira["key"])}</a> '
                   f'to Jira via Atlassian MCP.'))
    ev.sort(key=lambda e: e[1])
    items = "".join(f'''<li class="feed__item">
        <span class="feed__actor">{esc(actor)}</span>
        <span class="feed__time">{_fmt_ts(ts)}</span>
        <span class="feed__msg">{msg}</span></li>''' for actor, ts, msg in ev)
    return f'''<section class="panel" id="activity">
      <div class="panel__head"><h2>Agent Activity</h2>
        <p class="panel__sub">One invocation, one department's shift — Listen → Understand → Quantify → Validate → Dispatch.</p></div>
      <ol class="feed">{items}</ol>
    </section>'''


def validation_panel(v: dict) -> str:
    if not v:
        return ""
    bars = "".join(f'''<div class="f1row"><span class="f1row__k">{esc(k)}</span>
        <span class="f1row__track"><span class="f1row__fill" style="width:{round(f*100)}%"></span></span>
        <span class="f1row__v">{f:.3f}</span></div>'''
        for k, f in sorted(v["per_class_f1"].items(), key=lambda x: -x[1]))
    intent = v.get("intent_level")
    intent_row = ""
    if intent:
        intent_row = f'''<div class="valintent">
          <span class="valintent__k">Harder task — {intent["n_classes"]}-class intent theming:</span>
          <span>κ <strong>{intent["cohen_kappa"]}</strong></span>
          <span>macro-F1 <strong>{intent["macro_f1"]}</strong></span>
          <span>acc <strong>{intent["accuracy"]}</strong></span>
        </div>'''
    caveat = f'<p class="caveat">⚠ {esc(v["caveat"])}</p>' if v.get("caveat") else ""
    return f'''<section class="panel" id="validation">
      <div class="panel__head"><h2>Validation — is the theming trustworthy?</h2>
        <p class="panel__sub">{esc(v["method"])}</p></div>
      <div class="valgrid">
        <div class="valbig">
          <div class="valbig__item"><span>{v["cohen_kappa"]}</span><small>Cohen's κ · {esc(v["kappa_band"])}</small></div>
          <div class="valbig__item"><span>{v["macro_f1"]}</span><small>macro-F1 (11 themes)</small></div>
          <div class="valbig__item"><span>{v["accuracy"]}</span><small>accuracy</small></div>
          <div class="valbig__item"><span>{v["heldout_count"]}</span><small>held-out labels</small></div>
        </div>
        <div class="f1s">{bars}</div>
      </div>
      {intent_row}
      {caveat}
    </section>'''


def assumptions_panel(a: dict) -> str:
    asm = a["assumptions"]
    g = asm["globals"]
    rows = "".join(f'''<tr><td>{esc(k)}</td>
        <td class="num">{int(m["at_risk_rate"]*100)}%</td>
        <td class="num">{krw(m["value_per_case_krw"])}</td>
        <td>{esc(m["basis"])}</td></tr>'''
        for k, m in asm["categories"].items())
    srcs = "".join(f'<li>{esc(s["claim"])} — <a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["source"])}</a></li>'
                   for s in asm["sources"])
    return f'''<section class="panel" id="assumptions">
      <details class="assump">
        <summary><h2>Assumptions & sources <span class="assump__hint">the ₩ model is auditable — expand</span></h2></summary>
        <p class="panel__sub">{esc(g["note"])} Assumed AOV = {krw(g["aov_krw"])}.</p>
        <div class="tablewrap"><table class="atable">
          <thead><tr><th>Category</th><th class="num">At-risk rate</th><th class="num">₩ / case</th><th>Basis</th></tr></thead>
          <tbody>{rows}</tbody></table></div>
        <ul class="srcs">{srcs}</ul>
      </details>
    </section>'''


# ─────────────────────────────────────────────────────────── shell ─────────
CSS = r"""
:root{
  --bg:#0E1420; --panel:#161E2E; --panel-2:#1C2740; --line:#26314A;
  --ink:#E8ECF4; --muted:#8A96AD; --accent:#34B79A; --accent-ink:#0C1A16;
  --sev-high:#E5484D; --sev-med:#F5A623; --sev-low:#64708A; --good:#34B79A;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,"Cascadia Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --shadow:0 1px 0 rgba(255,255,255,.03),0 8px 24px -12px rgba(0,0,0,.6);
}
@media (prefers-color-scheme:light){
  :root{ --bg:#EEF1F6; --panel:#FFFFFF; --panel-2:#F5F7FA; --line:#DCE2ED;
    --ink:#16202E; --muted:#5A6678; --shadow:0 1px 0 rgba(0,0,0,.02),0 10px 30px -18px rgba(20,32,50,.35);}
}
:root[data-theme="dark"]{ --bg:#0E1420; --panel:#161E2E; --panel-2:#1C2740; --line:#26314A;
  --ink:#E8ECF4; --muted:#8A96AD; --shadow:0 1px 0 rgba(255,255,255,.03),0 8px 24px -12px rgba(0,0,0,.6);}
:root[data-theme="light"]{ --bg:#EEF1F6; --panel:#FFFFFF; --panel-2:#F5F7FA; --line:#DCE2ED;
  --ink:#16202E; --muted:#5A6678; --shadow:0 1px 0 rgba(0,0,0,.02),0 10px 30px -18px rgba(20,32,50,.35);}

*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  line-height:1.5;-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums;}
.wrap{max-width:1160px;margin:0 auto;padding:0 20px 72px;}
a{color:var(--accent);text-decoration:none;} a:hover{text-decoration:underline;}
h1,h2,h3{text-wrap:balance;margin:0;letter-spacing:-.01em;}
code{font-family:var(--mono);font-size:.86em;}

/* header */
.top{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line);}
.top__in{max-width:1160px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
.brand{display:flex;flex-direction:column;gap:2px;margin-right:auto;}
.brand__k{font-family:var(--mono);font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);}
.brand__t{font-size:18px;font-weight:650;}
.brand__t span{color:var(--muted);font-weight:450;}
.live{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;
  color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:4px 10px;}
.live::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--accent);
  box-shadow:0 0 0 0 var(--accent);animation:pulse 2.4s infinite;}
@keyframes pulse{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 60%,transparent)}70%{box-shadow:0 0 0 7px transparent}100%{box-shadow:0 0 0 0 transparent}}
.tbtn{font-family:var(--mono);font-size:12px;color:var(--ink);background:var(--panel);
  border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer;}
.tbtn:hover{border-color:var(--accent);}

/* hero line */
.hero{padding:34px 0 8px;}
.hero h1{font-size:clamp(26px,4.4vw,42px);font-weight:680;line-height:1.08;}
.hero .accent{color:var(--accent);}
.hero p{color:var(--muted);max-width:64ch;margin:12px 0 0;font-size:15px;}

/* KPI strip */
.strip{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin:26px 0 8px;}
@media (max-width:1100px){.strip{grid-template-columns:repeat(3,1fr);}}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:var(--shadow);
  display:flex;flex-direction:column;gap:6px;min-height:112px;}
.kpi__label{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;}
.kpi__value{font-family:var(--mono);font-size:26px;font-weight:600;letter-spacing:-.02em;line-height:1;}
.kpi__sub{font-size:12px;color:var(--muted);margin-top:auto;}
.kpi--accent .kpi__value{color:var(--accent);}
.kpi--sev .kpi__value{color:var(--sev-high);}
.kpi--good .kpi__value{color:var(--good);}

/* panels */
.panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;
  padding:24px;margin-top:22px;box-shadow:var(--shadow);}
.panel__head{margin-bottom:18px;}
.panel h2{font-size:19px;font-weight:640;}
.panel__sub{color:var(--muted);font-size:13.5px;margin:8px 0 0;max-width:78ch;}

/* truth map */
.themes{display:flex;flex-direction:column;gap:8px;}
.theme{border:1px solid var(--line);border-radius:12px;background:var(--panel-2);overflow:hidden;}
.theme>summary{list-style:none;cursor:pointer;padding:14px 16px;display:flex;flex-direction:column;gap:10px;}
.theme>summary::-webkit-details-marker{display:none;}
.theme__head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;}
.theme__name{font-weight:620;font-size:15px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.theme__rar{font-family:var(--mono);font-size:17px;font-weight:600;color:var(--accent);white-space:nowrap;}
.theme__bar{display:block;height:8px;border-radius:6px;background:color-mix(in srgb,var(--line) 60%,transparent);overflow:hidden;}
.theme__fill{display:block;height:100%;width:var(--bar);background:var(--sev);border-radius:6px;
  transition:width .8s cubic-bezier(.2,.8,.2,1);}
.theme__meta{display:flex;align-items:center;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:12.5px;}
.senti{display:flex;align-items:center;gap:7px;}
.senti__track{width:60px;height:5px;border-radius:4px;background:color-mix(in srgb,var(--line) 60%,transparent);overflow:hidden;}
.senti__fill{display:block;height:100%;background:var(--sev-high);}
.chev{margin-left:auto;color:var(--accent);font-size:12px;}
.trend{font-family:var(--mono);font-size:11px;padding:1px 7px;border-radius:999px;border:1px solid var(--line);}
.trend--up{color:var(--sev-high);border-color:color-mix(in srgb,var(--sev-high) 40%,transparent);}
.trend--down{color:var(--good);border-color:color-mix(in srgb,var(--good) 40%,transparent);}
.trend--flat{color:var(--muted);}
.sev-pill{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.05em;
  padding:2px 7px;border-radius:999px;border:1px solid transparent;}
.sev-pill--high{color:var(--sev-high);border-color:color-mix(in srgb,var(--sev-high) 45%,transparent);background:color-mix(in srgb,var(--sev-high) 12%,transparent);}
.sev-pill--medium{color:var(--sev-med);border-color:color-mix(in srgb,var(--sev-med) 45%,transparent);background:color-mix(in srgb,var(--sev-med) 12%,transparent);}
.sev-pill--low{color:var(--sev-low);border-color:color-mix(in srgb,var(--sev-low) 45%,transparent);background:color-mix(in srgb,var(--sev-low) 12%,transparent);}
.arm-tag{font-family:var(--mono);font-size:10px;color:var(--muted);border:1px solid var(--line);border-radius:6px;padding:2px 6px;}
.theme__body{padding:0 16px 16px;display:flex;flex-direction:column;gap:12px;}
.theme__mech{margin:0;font-size:13.5px;}
.theme__basis{margin:0;font-size:12.5px;color:var(--muted);border-left:2px solid var(--accent);padding-left:10px;}
.reps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px;}
.reps li{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 12px;display:flex;flex-direction:column;gap:5px;}
.rep__meta{display:flex;gap:10px;align-items:center;font-size:11.5px;color:var(--muted);flex-wrap:wrap;}
.rep__intent{font-family:var(--mono);color:var(--accent);}
.rep__w{font-family:var(--mono);color:var(--muted);}
.rep__conf{font-family:var(--mono);}
.rep__quote{font-size:13.5px;}
.imix{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:11.5px;}
.imix__k{color:var(--muted);font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;}
.ichip{display:inline-flex;align-items:center;gap:5px;background:var(--panel);border:1px solid var(--line);
  border-radius:999px;padding:2px 4px 2px 9px;font-family:var(--mono);}
.ichip__n{background:color-mix(in srgb,var(--line) 55%,transparent);border-radius:999px;padding:1px 6px;color:var(--ink);}
.ichip__w{border-radius:999px;padding:1px 6px;font-size:10px;}
.ichip__w--info{color:var(--sev-low);} .ichip__w--fric{color:var(--sev-med);} .ichip__w--churn{color:var(--sev-high);}

/* flip cards */
.flips{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;}
.flip{perspective:1200px;min-height:212px;border-radius:14px;outline:none;}
.flip__inner{position:relative;width:100%;height:100%;min-height:212px;transition:transform .6s cubic-bezier(.2,.8,.2,1);transform-style:preserve-3d;}
.flip:hover .flip__inner,.flip:focus .flip__inner,.flip:focus-within .flip__inner{transform:rotateY(180deg);}
.flip__face{position:absolute;inset:0;backface-visibility:hidden;border:1px solid var(--line);
  border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:9px;background:var(--panel-2);}
.flip__back{transform:rotateY(180deg);background:linear-gradient(180deg,var(--panel-2),var(--panel));}
.artifact__badge{font-family:var(--mono);font-size:10.5px;letter-spacing:.04em;color:var(--accent);
  border:1px solid color-mix(in srgb,var(--accent) 40%,transparent);border-radius:999px;padding:3px 9px;align-self:flex-start;}
.artifact__badge--jira{color:#8FA0FF;border-color:color-mix(in srgb,#8FA0FF 40%,transparent);}
.flip h3{font-size:16px;font-weight:630;}
.artifact__prob{font-size:12.5px;color:var(--muted);margin:0;}
.artifact__num{margin-top:auto;display:flex;align-items:baseline;gap:7px;}
.artifact__num span{font-family:var(--mono);font-size:20px;font-weight:600;color:var(--accent);}
.artifact__num small{color:var(--muted);font-size:11px;}
.flip__hint{font-size:11px;color:var(--muted);margin-top:auto;}
.artifact__title{font-size:13px;font-weight:560;margin:0;}
.artifact__cta{font-family:var(--mono);font-size:12.5px;margin-top:auto;align-self:flex-start;
  border:1px solid var(--accent);border-radius:8px;padding:7px 12px;color:var(--accent);}
.artifact__cta:hover{background:var(--accent);color:var(--accent-ink);text-decoration:none;}
.artifact__cta--file{color:var(--muted);border-color:var(--line);}
.viatag{font-family:var(--mono);font-size:10px;color:var(--muted);}
.diff{font-family:var(--mono);font-size:10.5px;line-height:1.45;background:var(--bg);border:1px solid var(--line);
  border-radius:8px;padding:9px;margin:0;overflow-x:auto;max-height:96px;}
.diff .add{display:block;color:var(--good);white-space:pre-wrap;}

/* feed */
.feed{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;}
.feed__item{display:grid;grid-template-columns:104px 92px 1fr;gap:12px;align-items:baseline;
  padding:11px 0;border-top:1px dashed var(--line);}
.feed__item:first-child{border-top:none;}
.feed__actor{font-family:var(--mono);font-size:11px;color:var(--accent);text-transform:uppercase;letter-spacing:.05em;}
.feed__time{font-family:var(--mono);font-size:11px;color:var(--muted);}
.feed__msg{font-size:13.5px;}

/* validation */
.valgrid{display:grid;grid-template-columns:1fr 1.3fr;gap:22px;}
.valbig{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;align-content:start;}
.valbig__item{background:var(--panel-2);border:1px solid var(--line);border-radius:12px;padding:16px;}
.valbig__item span{font-family:var(--mono);font-size:28px;font-weight:600;color:var(--good);display:block;}
.valbig__item small{color:var(--muted);font-size:12px;}
.f1s{display:flex;flex-direction:column;gap:7px;}
.f1row{display:grid;grid-template-columns:100px 1fr 48px;gap:10px;align-items:center;font-size:12.5px;}
.f1row__k{color:var(--muted);}
.f1row__track{height:7px;border-radius:5px;background:color-mix(in srgb,var(--line) 60%,transparent);overflow:hidden;}
.f1row__fill{display:block;height:100%;background:var(--good);}
.f1row__v{font-family:var(--mono);text-align:right;}
.valintent{display:flex;gap:18px;flex-wrap:wrap;align-items:center;margin-top:16px;padding:12px 14px;
  background:var(--panel-2);border:1px solid var(--line);border-radius:10px;font-size:13px;}
.valintent__k{color:var(--muted);} .valintent strong{font-family:var(--mono);color:var(--good);}
.caveat{margin:14px 0 0;font-size:12.5px;color:var(--muted);line-height:1.6;
  border-left:2px solid var(--sev-med);padding-left:12px;}

/* assumptions */
.assump summary{list-style:none;cursor:pointer;}
.assump summary::-webkit-details-marker{display:none;}
.assump summary h2{display:flex;align-items:center;gap:12px;}
.assump__hint{font-family:var(--mono);font-size:11px;font-weight:400;color:var(--accent);}
.tablewrap{overflow-x:auto;margin-top:14px;}
.atable{width:100%;border-collapse:collapse;font-size:12.5px;min-width:640px;}
.atable th,.atable td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;}
.atable th{color:var(--muted);font-weight:550;text-transform:uppercase;font-size:11px;letter-spacing:.04em;}
.atable td.num,.atable th.num{text-align:right;font-family:var(--mono);white-space:nowrap;}
.srcs{margin:14px 0 0;padding-left:18px;color:var(--muted);font-size:12.5px;display:flex;flex-direction:column;gap:5px;}

.foot{color:var(--muted);font-size:12px;text-align:center;margin-top:30px;line-height:1.7;}
.foot code{color:var(--ink);}
@media (max-width:880px){
  .strip{grid-template-columns:repeat(2,1fr);} .valgrid{grid-template-columns:1fr;}
  .feed__item{grid-template-columns:88px 1fr;} .feed__time{grid-column:2;}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;}}
"""

JS = r"""
(function(){
  var root=document.documentElement;
  var saved=localStorage.getItem('voc-theme');
  if(saved) root.setAttribute('data-theme',saved);
  function cur(){return root.getAttribute('data-theme')|| (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');}
  var b=document.getElementById('themebtn');
  function label(){b.textContent = cur()==='dark' ? '◐ Light' : '◑ Dark';}
  label();
  b.addEventListener('click',function(){var n=cur()==='dark'?'light':'dark';root.setAttribute('data-theme',n);localStorage.setItem('voc-theme',n);label();});
  // animate bars into view
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.style.setProperty('--bar', e.target.dataset.bar||'');io.unobserve(e.target);}})});
})();
"""


def render() -> str:
    a = _load("analysis.json")
    v = _load("validation.json")
    disp = _load("dispatched.json", {"dispatched": []})
    meta = _load("ingest_meta.json")
    jira = _load("jira_dispatch.json")
    if not a:
        raise SystemExit("[dashboard] analysis.json missing — run analyze.py first")

    total = krw(a["total_revenue_at_risk_krw"])
    intent_v = (v or {}).get("intent_level") or {}
    band = round((1 - intent_v.get("macro_f1", 1.0)) * 100, 1) if intent_v else None
    n_real = len([d for d in disp.get("dispatched", []) if d.get("executed")]) + (1 if jira else 0)
    body = "\n".join([
        exec_strip(a, v, disp, jira),
        truth_map(a),
        artifact_cards(disp, jira, a),
        validation_panel(v),
        activity_feed(a, v, disp, meta, jira),
        assumptions_panel(a),
    ])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Channel VOC Intelligence Dept. — Daily Customer Truth</title>
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="top__in">
  <div class="brand">
    <span class="brand__k">Channel VOC Intelligence Dept.</span>
    <span class="brand__t">Daily Customer Truth <span>· {esc(a['day'])}</span></span>
  </div>
  <span class="live">live · {n_real} real actions dispatched</span>
  <button class="tbtn" id="themebtn" type="button">◑ Dark</button>
</div></header>
<main class="wrap">
  <div class="hero">
    <h1>Yesterday, <span class="accent">{a['inbox_count']:,}</span> real conversations became
      <span class="accent">{total}</span> of ranked, actionable customer truth.</h1>
    <p>One invocation read the entire inbox, quantified where revenue is leaking, validated the theming against
      held-out human labels, and dispatched real engineering, help-center, and CSM actions — with every figure
      traceable to the exact conversations it came from.{f' The ₩ total carries a ±{band}% band from theming misassignment (27-class intent macro-F1 {intent_v.get("macro_f1")}).' if band is not None else ''}</p>
  </div>
  {body}
  <p class="foot">
    Source: real public customer-support conversations · <code>{esc(a['source']['dataset'])}</code> ({esc(a['source']['license'])}).<br/>
    Counts are measured; ₩ conversion is a stated, auditable assumption model. Generated by the plugin pipeline — <code>run.py</code>.
  </p>
</main>
<script>{JS}</script>
</body>
</html>"""


def main() -> int:
    OUT.mkdir(exist_ok=True)
    htmlout = render()
    (OUT / "dashboard.html").write_text(htmlout, encoding="utf-8")
    print(f"[dashboard] wrote out/dashboard.html ({len(htmlout):,} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
