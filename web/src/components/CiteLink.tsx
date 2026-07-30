// Cite drilldown (§2.4) — turns graph ID tokens inside an answer into clickable
// inline links so the operator can traverse the graph as a conversation. Tokens
// only, mono for ids (DESIGN.md: all ids/₩/scores are mono).
import type { ReactNode } from "react";

// Known ID prefixes emitted by the graph backend:
//   rc_<COMPONENT> (rootcause), conv_00000 (conversation), sym_* (symptom),
//   comp_* (component), act_* (action), cust_* (customer).
export const CITE_PREFIXES = ["rc", "sym", "conv", "comp", "act", "cust"] as const;

// <prefix>_<token>, token = [A-Za-z0-9] segments joined by "_" (uppercase/digits
// allowed). A leading \b keeps prefixes from matching inside longer words
// (e.g. "contact_us" does not yield an act_ cite).
export const CITE_RE = new RegExp(
  `\\b(?:${CITE_PREFIXES.join("|")})_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*`,
  "g",
);

export function citeQuestion(id: string): string {
  return `${id} 근거 대화 보여줘`;
}

// ₩ amounts and labelled scores (DESIGN.md: 금액·점수 mono) — display-only, not
// clickable like ID cites. Deliberately scoped to just these two shapes, not
// every digit in the prose: plain counts/ordinals ("근거 49건", "Top3") aren't
// graph-derived values per DESIGN.md and would just add visual noise if mono'd.
const CURRENCY_RE = /₩[\d,]+/g;
// Only the trailing number is wrapped — the label word stays regular prose.
const SCORE_RE = /\b(confidence|bm25|cos-sim|RRF\s*k)([:=\s]+)([\d.]+)/gi;

// Splits a plain-text run (already known to contain no ID cite) into mono
// currency/score spans + the untouched text between them, in document order.
function monoNumbers(text: string, keyPrefix: string): ReactNode[] {
  const hits: { start: number; end: number; value: string }[] = [];

  const currencyRe = new RegExp(CURRENCY_RE.source, CURRENCY_RE.flags);
  let m: RegExpExecArray | null;
  while ((m = currencyRe.exec(text)) !== null) {
    hits.push({ start: m.index, end: m.index + m[0].length, value: m[0] });
  }

  const scoreRe = new RegExp(SCORE_RE.source, SCORE_RE.flags);
  while ((m = scoreRe.exec(text)) !== null) {
    const [, label, sep, num] = m;
    const numStart = m.index + label.length + sep.length;
    hits.push({ start: numStart, end: numStart + num.length, value: num });
  }

  hits.sort((a, b) => a.start - b.start);

  const parts: ReactNode[] = [];
  let last = 0;
  hits.forEach((h, i) => {
    if (h.start < last) return; // overlap guard, shouldn't happen given the two shapes above
    if (h.start > last) parts.push(text.slice(last, h.start));
    parts.push(
      <span key={`${keyPrefix}-num-${i}`} className="mono">
        {h.value}
      </span>,
    );
    last = h.end;
  });
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export interface CiteTextProps {
  text: string;
  onCite: (id: string) => void;
  // While a question is in flight the stream is busy; disable cites so a click
  // isn't silently swallowed by the submit guard (visual + functional feedback).
  disabled?: boolean;
}

export function CiteText({ text, onCite, disabled = false }: CiteTextProps) {
  const parts: ReactNode[] = [];
  const re = new RegExp(CITE_RE.source, CITE_RE.flags);
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(...monoNumbers(text.slice(last, m.index), `pre${key}`));
    const id = m[0];
    parts.push(
      <button
        key={`cite-${key++}`}
        type="button"
        className="cite mono"
        disabled={disabled}
        onClick={() => onCite(id)}
      >
        {id}
      </button>,
    );
    last = m.index + id.length;
  }
  if (last < text.length) parts.push(...monoNumbers(text.slice(last), `post${key}`));

  return <>{parts}</>;
}
