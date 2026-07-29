// Copilot chat API client — POST /api/chat (router-chat #14).
// Answers are composed from real graph values server-side; the client only
// transports and parses them (no client-side answer regeneration).

export interface ChatRequest {
  message: string;
  thread_id?: string;
}

export interface ChatResponse {
  answer: string;
  arms: string[];
  subgraph_ref: Record<string, unknown> | null;
  confidence: number;
  gate: "refuse" | "low_confidence" | "answer";
  related_questions: string[];
  interrupt_payload: Record<string, unknown> | null;
  // Per-hit retrieval evidence for the panel (#49) — structurally an EvidenceItem[].
  evidence: { id: string; arms: string[]; score: number }[];
}

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export async function postChat(
  req: ChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });

  if (!res.ok) {
    // serve.py wraps failures in a {"error": "..."} envelope; fall back to
    // statusText when the body is missing or not JSON.
    let message = res.statusText;
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) message = body.error;
    } catch {
      /* keep statusText */
    }
    throw new Error(message);
  }

  return (await res.json()) as ChatResponse;
}
