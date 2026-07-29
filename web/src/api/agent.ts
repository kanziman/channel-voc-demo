// Agent API client — POST /api/agent/dispatch (router-agent #16). Resumes a
// LangGraph interrupt on Neo4j: approve dispatches the issue, reject resolves the
// thread as rejected.

export interface InterruptCandidate {
  root_cause_key: string;
  component: string;
  title: string;
  revenue_at_risk_krw: number;
  confidence?: number;
  cited_conv_ids?: string[];
}
export interface InterruptPayload {
  message: string;
  candidates: InterruptCandidate[];
}
export interface DispatchedAction {
  key: string;
  root_cause_key: string;
  title: string;
  url: string | null;
  status: string;
  revenue_at_risk_krw: number;
  cited: string[];
}
export interface DispatchResponse {
  thread_id: string;
  status: "dispatched" | "rejected";
  dispatched: DispatchedAction[];
}
export interface DispatchRequest {
  thread_id: string;
  decision: "approve" | "reject" | string | string[];
}

export interface RootCause {
  key: string;
  component: string;
  frequency: number;
  revenue_at_risk_krw: number;
  projected_recoverable_krw: number;
  severity_avg: number;
  confidence_avg: number;
  hypothesis: string;
}
export interface RunResponse {
  thread_id: string;
  interrupt: InterruptPayload | null;
  dispatched: DispatchedAction[] | null;
}

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export async function postDispatch(
  req: DispatchRequest,
  signal?: AbortSignal,
): Promise<DispatchResponse> {
  const res = await fetch(`${API_BASE}/api/agent/dispatch`, {
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
  return (await res.json()) as DispatchResponse;
}

async function unwrap<T>(res: Response): Promise<T> {
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
  return (await res.json()) as T;
}

export async function getRootcauses(signal?: AbortSignal): Promise<{ rootcauses: RootCause[] }> {
  const res = await fetch(`${API_BASE}/api/agent/rootcauses`, { signal });
  return unwrap<{ rootcauses: RootCause[] }>(res);
}

export async function postRun(live = false, signal?: AbortSignal): Promise<RunResponse> {
  const res = await fetch(`${API_BASE}/api/agent/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ live }),
    signal,
  });
  return unwrap<RunResponse>(res);
}
