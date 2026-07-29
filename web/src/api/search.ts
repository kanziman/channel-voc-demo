// Hybrid search API client — POST /api/search/hybrid (router-search #13). Thin
// wrapper over the existing hybrid_search; the per-result arms/rrf contract feeds
// the 3-column console.

export interface HybridSearchRequest {
  query: string;
  k?: number;
}
export interface HybridResult {
  id: string;
  dense: number | null;
  sparse: number | null;
  in_graph: boolean;
  text?: string | null;
  component?: string | null;
  severity?: number | null;
  rrf: number;
  arms: string[];
}
export interface HybridSearchResponse {
  query: string;
  top_component: string | null;
  counts: Record<string, number>;
  results: HybridResult[];
}

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export async function postSearch(
  req: HybridSearchRequest,
  signal?: AbortSignal,
): Promise<HybridSearchResponse> {
  const res = await fetch(`${API_BASE}/api/search/hybrid`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });

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
  return (await res.json()) as HybridSearchResponse;
}
