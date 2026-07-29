// In-chat approval gate (§2, HITL demo highlight). When a root-cause answer
// carries an interrupt payload, this card lets the operator approve → dispatch a
// GitHub issue (with provenance) or reject → resolve the thread. Maps LangGraph's
// interrupt()/Command(resume) onto POST /api/agent/dispatch. Tokens only.
import { useState } from "react";
import { postDispatch } from "../api/agent";
import type { DispatchRequest, DispatchResponse, InterruptPayload } from "../api/agent";

export interface ApprovalCardProps {
  interruptPayload: InterruptPayload | null;
  threadId: string;
  dispatchFn?: (req: DispatchRequest) => Promise<DispatchResponse>;
  onResolved?: (res: DispatchResponse) => void;
}

const won = (n: number) => `₩${new Intl.NumberFormat("ko-KR").format(n)}`;

export function ApprovalCard({
  interruptPayload,
  threadId,
  dispatchFn = postDispatch,
  onResolved,
}: ApprovalCardProps) {
  const [result, setResult] = useState<DispatchResponse | null>(null);
  const [dispatching, setDispatching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!interruptPayload) return null;

  function decide(decision: "approve" | "reject") {
    if (dispatching) return; // guard against double-submit before the button disables
    setDispatching(true);
    setError(null);
    dispatchFn({ thread_id: threadId, decision })
      .then((res) => {
        setResult(res);
        onResolved?.(res);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setDispatching(false));
  }

  return (
    <div className="approval-card" data-testid="approval-card">
      <div className="ac-h mono">승인 게이트 · <span className="mono">{threadId}</span></div>
      <p className="ac-msg">{interruptPayload.message}</p>

      <ul className="ac-candidates">
        {interruptPayload.candidates.map((c) => (
          <li key={c.root_cause_key} className="ac-candidate">
            <span className="ac-action">{c.title}</span>
            <span className="ac-target">{c.component}</span>
            <span className="ac-risk mono">{won(c.revenue_at_risk_krw)}</span>
          </li>
        ))}
      </ul>

      {result ? (
        result.status === "rejected" ? (
          <p className="ac-result mono">반려됨</p>
        ) : (
          <ul className="ac-dispatched">
            {result.dispatched.map((a) => (
              <li key={a.key} className="ac-issue">
                <span className="ac-prov mono">{a.key}</span>
                {a.url ? (
                  <a className="ac-link" href={a.url} target="_blank" rel="noreferrer">
                    {a.url}
                  </a>
                ) : (
                  <span className="ac-status mono">{a.status}</span>
                )}
              </li>
            ))}
          </ul>
        )
      ) : (
        <div className="ac-actions">
          <button
            type="button"
            className="ac-approve"
            disabled={dispatching}
            onClick={() => decide("approve")}
          >
            승인
          </button>
          <button
            type="button"
            className="ac-reject"
            disabled={dispatching}
            onClick={() => decide("reject")}
          >
            반려
          </button>
        </div>
      )}

      {error && <p className="ac-error" role="alert">오류: {error}</p>}
    </div>
  );
}
