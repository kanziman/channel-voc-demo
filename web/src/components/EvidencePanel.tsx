// Evidence panel (§2.5) — draws the GraphRAG subgraph behind an answer and lists
// the retrieval evidence (D/S/G arm tags + score). "⤢ 탐색" opens the 3-tab
// console. Tokens only, no gradients — the single exception is the RootCause
// node glow (--glow-rootcause), rendered on cytoscape via an underlay.
import { useEffect, useState } from "react";
import type { ElementDefinition } from "cytoscape";
import CytoscapeComponent from "react-cytoscapejs";

// Structural cytoscape stylesheet rule (decoupled from @types/cytoscape's
// version-specific Stylesheet union).
export interface CyStyleRule {
  selector: string;
  style: Record<string, string | number>;
}
import { getSubgraph } from "../api/graph";
import type { SubgraphQuery, SubgraphResponse } from "../api/graph";

export interface EvidenceItem {
  id: string;
  arms: string[];
  score: number;
  label?: string;
}
export interface EvidenceSubgraphRef {
  top_component?: string;
  root_cause_key?: string;
  conversation_ids?: string[];
}
export interface EvidencePanelProps {
  subgraphRef: EvidenceSubgraphRef | null;
  evidence?: EvidenceItem[];
  onExplore?: () => void;
  getSubgraphFn?: (q?: SubgraphQuery) => Promise<SubgraphResponse>;
}

// D/S/G — the load-bearing arm visual language (backend name → key).
const ARM_LETTER: Record<string, string> = { dense: "D", sparse: "S", graph: "G" };
const ARM_ORDER = ["dense", "sparse", "graph"] as const;

// Node fill by ontology type. cytoscape renders on canvas (needs a JS color
// string), so we resolve the design token at runtime and keep a literal only as
// a graceful fallback when the var can't be read (e.g. jsdom).
const NODE_TOKEN: Record<string, string> = {
  RootCause: "--node-rootcause",
  Component: "--node-component",
  Symptom: "--node-symptom",
  Conversation: "--node-conversation",
};
const NODE_FALLBACK: Record<string, string> = {
  RootCause: "#e8a13a",
  Component: "#5b9bd5",
  Symptom: "#ec835a",
  Conversation: "#8e6fd8",
};
const DEFAULT_NODE = "#8a897f"; // --muted

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function colorForType(type: string): string {
  const token = NODE_TOKEN[type];
  const fallback = NODE_FALLBACK[type] ?? DEFAULT_NODE;
  return token ? cssVar(token, fallback) : fallback;
}

export function toElements(sub: SubgraphResponse): ElementDefinition[] {
  const nodes: ElementDefinition[] = sub.nodes.map((n) => ({
    data: { id: n.id, type: n.type, label: n.label, color: colorForType(n.type) },
  }));
  const edges: ElementDefinition[] = sub.edges.map((e) => ({
    data: { source: e.source, target: e.target, type: e.type },
  }));
  return [...nodes, ...edges];
}

export function graphStylesheet(glow: string): CyStyleRule[] {
  return [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        label: "data(label)",
        color: "#e8e6df",
        "font-size": 9,
        "text-valign": "bottom",
        "text-margin-y": 3,
        width: 18,
        height: 18,
      },
    },
    {
      // The single glow exception: RootCause only (§ DESIGN.md). --glow-rootcause
      // is a CSS drop-shadow filter; the canvas equivalent is a colored underlay.
      selector: 'node[type="RootCause"]',
      style: {
        "underlay-color": glow,
        "underlay-opacity": 0.45,
        "underlay-padding": 6,
      },
    },
    {
      selector: "edge",
      style: {
        width: 1,
        "line-color": "#3d3b37",
        "target-arrow-color": "#3d3b37",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
      },
    },
  ];
}

export function EvidencePanel({
  subgraphRef,
  evidence = [],
  onExplore,
  getSubgraphFn = getSubgraph,
}: EvidencePanelProps) {
  const [graph, setGraph] = useState<SubgraphResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!subgraphRef) {
      setGraph(null);
      setFailed(false);
      return;
    }
    let alive = true;
    setGraph(null);
    setFailed(false);
    const query: SubgraphQuery | undefined = subgraphRef.root_cause_key
      ? { expand: `rc::${subgraphRef.root_cause_key}`, hops: 1 }
      : undefined;
    const p = query ? getSubgraphFn(query) : getSubgraphFn();
    p.then((g) => alive && setGraph(g)).catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [subgraphRef, getSubgraphFn]);

  // --glow-rootcause is a CSS drop-shadow filter and can't feed cytoscape's
  // underlay-color (a solid color), so the canvas glow uses the RootCause node
  // color (--node-rootcause); the RootCause-only exception is what matters (§DESIGN).
  const glow = cssVar("--node-rootcause", "#e8a13a");

  return (
    <aside className="evidence">
      <div className="ev-h mono">근거 서브그래프</div>

      <div className="ev-canvas">
        {subgraphRef == null ? (
          <div className="ev-placeholder mono" data-testid="evidence-placeholder">
            답변을 선택하면 GraphRAG 서브그래프가 여기 그려집니다
          </div>
        ) : failed ? (
          <div className="ev-placeholder mono" data-testid="evidence-error">
            서브그래프를 불러오지 못했어요
          </div>
        ) : graph ? (
          <CytoscapeComponent
            elements={toElements(graph)}
            stylesheet={graphStylesheet(glow)}
            style={{ width: "100%", height: "100%" }}
            layout={{ name: "cose", animate: false, padding: 24 }}
          />
        ) : (
          <div className="ev-placeholder mono">서브그래프 불러오는 중…</div>
        )}
      </div>

      {evidence.length > 0 && (
        <ul className="ev-list">
          {evidence.map((item) => (
            <li key={item.id} className="ev-item" data-testid="evidence-item">
              <span className="ev-id mono">{item.id}</span>
              <span className="ev-arms">
                {ARM_ORDER.filter((a) => item.arms.includes(a)).map((a) => (
                  <span key={a} className="ev-arm mono" data-arm={ARM_LETTER[a]}>
                    {ARM_LETTER[a]}
                  </span>
                ))}
              </span>
              <span className="ev-score mono">{item.score}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="ev-actions">
        <button type="button" className="ev-explore" onClick={() => onExplore?.()}>
          ⤢ 탐색
        </button>
      </div>
    </aside>
  );
}
