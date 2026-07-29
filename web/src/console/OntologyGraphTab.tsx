// Console tab 1 — ontology & graph exploration (§2.5). Renders the ontology
// chain (Customer→Conversation→Symptom→Component→RootCause→Action) and expands a
// node 1/2 hops on click, merging the result. Reuses the evidence panel's
// cytoscape mapping + RootCause glow. Tokens only, no gradients (glow excepted).
import { useEffect, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import { getSubgraph } from "../api/graph";
import type { SubgraphQuery, SubgraphResponse } from "../api/graph";
import { graphStylesheet, toElements } from "../components/EvidencePanel";

export function mergeSubgraph(a: SubgraphResponse, b: SubgraphResponse): SubgraphResponse {
  const nodes = [...a.nodes];
  const seenNodes = new Set(a.nodes.map((n) => n.id));
  for (const n of b.nodes) {
    if (!seenNodes.has(n.id)) {
      seenNodes.add(n.id);
      nodes.push(n);
    }
  }
  const edgeKey = (e: { source: string; target: string; type: string }) =>
    `${e.source}->${e.target}:${e.type}`;
  const edges = [...a.edges];
  const seenEdges = new Set(a.edges.map(edgeKey));
  for (const e of b.edges) {
    if (!seenEdges.has(edgeKey(e))) {
      seenEdges.add(edgeKey(e));
      edges.push(e);
    }
  }
  return { nodes, edges, center: b.center ?? a.center };
}

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export interface OntologyGraphTabProps {
  getSubgraphFn?: (q?: SubgraphQuery) => Promise<SubgraphResponse>;
  initialHops?: 1 | 2;
}

export function OntologyGraphTab({
  getSubgraphFn = getSubgraph,
  initialHops = 1,
}: OntologyGraphTabProps) {
  const [graph, setGraph] = useState<SubgraphResponse | null>(null);
  const [hops, setHops] = useState<1 | 2>(initialHops);
  const [failed, setFailed] = useState(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    getSubgraphFn()
      .then((g) => alive.current && setGraph(g))
      .catch(() => alive.current && setFailed(true));
    return () => {
      alive.current = false;
    };
  }, [getSubgraphFn]);

  function expand(id: string) {
    getSubgraphFn({ expand: id, hops })
      .then((inc) => alive.current && setGraph((cur) => (cur ? mergeSubgraph(cur, inc) : inc)))
      .catch(() => {
        /* keep current graph on a failed expand */
      });
  }

  // Keep the latest expand closure reachable from the (once-bound) canvas tap.
  const expandRef = useRef(expand);
  expandRef.current = expand;

  // Bind cytoscape canvas node taps to the same expand handler as the node list.
  function bindCy(cyInstance: unknown) {
    const cy = cyInstance as {
      on: (ev: string, sel: string, h: (evt: { target: { id: () => string } }) => void) => void;
      off?: (ev: string, sel: string) => void;
    };
    cy.off?.("tap", "node");
    cy.on("tap", "node", (evt) => expandRef.current(evt.target.id()));
  }

  const glow = cssVar("--node-rootcause", "#e8a13a");

  return (
    <section className="console-tab" data-testid="ontology-tab">
      <div className="ct-controls">
        <span className="ct-label mono">HOPS</span>
        {([1, 2] as const).map((h) => (
          <button
            key={h}
            type="button"
            className={`ct-hop${hops === h ? " is-active" : ""}`}
            aria-pressed={hops === h}
            onClick={() => setHops(h)}
          >
            {h}-hop
          </button>
        ))}
      </div>

      {failed ? (
        <div className="ct-error mono" data-testid="ontology-error">
          온톨로지를 불러오지 못했어요
        </div>
      ) : graph ? (
        <>
          <div className="ct-canvas">
            <CytoscapeComponent
              elements={toElements(graph)}
              stylesheet={graphStylesheet(glow)}
              style={{ width: "100%", height: "100%" }}
              cy={bindCy}
            />
          </div>
          <ul className="ct-nodes">
            {graph.nodes.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  className="ct-node mono"
                  data-node-id={n.id}
                  onClick={() => expand(n.id)}
                  title={`${n.type} 확장`}
                >
                  {n.id}
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="ct-loading mono">온톨로지 불러오는 중…</div>
      )}
    </section>
  );
}
