// Graph API client — GET /api/graph/subgraph (router-graph #15). Node ids follow
// build_snapshot's scheme ("rc::rc_billing", "comp::billing", "conv::conv_00001").

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  [k: string]: unknown;
}
export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  [k: string]: unknown;
}
export interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  center: string | null;
}
export interface SubgraphQuery {
  expand?: string;
  hops?: 1 | 2;
}

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export async function getSubgraph(
  q?: SubgraphQuery,
  signal?: AbortSignal,
): Promise<SubgraphResponse> {
  const params = new URLSearchParams();
  if (q?.expand) params.set("expand", q.expand);
  if (q?.hops) params.set("hops", String(q.hops));
  const qs = params.toString();
  const url = `${API_BASE}/api/graph/subgraph${qs ? `?${qs}` : ""}`;

  const res = await fetch(url, { signal });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) message = body.error;
    } catch {
      /* keep statusText */
    }
    throw new Error(message);
  }
  return (await res.json()) as SubgraphResponse;
}
