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
    if (m.index > last) parts.push(text.slice(last, m.index));
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
  if (last < text.length) parts.push(text.slice(last));

  return <>{parts}</>;
}
