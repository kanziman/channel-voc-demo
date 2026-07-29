// Console tab 3 — root-cause approval center (§2.5). Aggregates rootcause.compute
// cards (₩risk / ₩recoverable / frequency / confidence, all mono) with per-card
// and bulk approve/reject. Each decision is a stateless run→dispatch roundtrip.
// Severity uses tokens only (good/warning/serious/critical), no gradients.
import { useEffect, useState } from "react";
import { getRootcauses, postDispatch, postRun } from "../api/agent";
import type { DispatchRequest, DispatchResponse, RootCause, RunResponse } from "../api/agent";

export type Severity = "good" | "warning" | "serious" | "critical";

export function severityBucket(severityAvg: number): Severity {
  if (severityAvg >= 0.8) return "critical";
  if (severityAvg >= 0.6) return "serious";
  if (severityAvg >= 0.4) return "warning";
  return "good";
}

export interface RootCauseGateTabProps {
  rootcausesFn?: () => Promise<{ rootcauses: RootCause[] }>;
  runFn?: (live?: boolean) => Promise<RunResponse>;
  dispatchFn?: (req: DispatchRequest) => Promise<DispatchResponse>;
}

const won = (n: number) => `₩${new Intl.NumberFormat("ko-KR").format(n)}`;
type CardState = "pending" | "dispatched" | "rejected";

export function RootCauseGateTab({
  rootcausesFn = getRootcauses,
  runFn = postRun,
  dispatchFn = postDispatch,
}: RootCauseGateTabProps) {
  const [rootcauses, setRootcauses] = useState<RootCause[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [states, setStates] = useState<Record<string, CardState>>({});
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const onActionError = (err: unknown) =>
    setActionError(err instanceof Error ? err.message : String(err));

  useEffect(() => {
    let alive = true;
    rootcausesFn()
      .then((r) => alive && setRootcauses(r.rootcauses))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [rootcausesFn]);

  // A decision is resolved statelessly: start a run (fresh thread) then dispatch.
  async function resolve(decision: DispatchRequest["decision"]): Promise<DispatchResponse> {
    const run = await runFn();
    return dispatchFn({ thread_id: run.thread_id, decision });
  }

  function mark(keys: string[], state: CardState) {
    setStates((s) => ({ ...s, ...Object.fromEntries(keys.map((k) => [k, state])) }));
  }

  function approveOne(key: string) {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    resolve([key])
      .then(() => mark([key], "dispatched"))
      .catch(onActionError)
      .finally(() => setBusy(false));
  }

  function rejectOne(key: string) {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    resolve("reject")
      .then(() => mark([key], "rejected"))
      .catch(onActionError)
      .finally(() => setBusy(false));
  }

  function bulk(decision: "approve" | "reject") {
    if (busy || !rootcauses) return;
    setBusy(true);
    setActionError(null);
    const keys = rootcauses.map((rc) => rc.key);
    resolve(decision)
      .then(() => mark(keys, decision === "approve" ? "dispatched" : "rejected"))
      .catch(onActionError)
      .finally(() => setBusy(false));
  }

  return (
    <section className="console-tab gate-tab" data-testid="rootcause-gate-tab">
      <div className="rc-bulk">
        <span className="ct-label mono">루트원인 승인 센터</span>
        <button type="button" className="rc-approve-all" disabled={busy} onClick={() => bulk("approve")}>
          일괄 승인
        </button>
        <button type="button" className="rc-reject-all" disabled={busy} onClick={() => bulk("reject")}>
          일괄 반려
        </button>
      </div>

      {actionError && (
        <p className="rc-action-error" role="alert" data-testid="rc-action-error">
          디스패치 실패: {actionError}
        </p>
      )}

      {failed ? (
        <div className="rc-error mono" data-testid="rc-error">루트원인을 불러오지 못했어요</div>
      ) : rootcauses ? (
        <ul className="rc-cards">
          {rootcauses.map((rc) => {
            const state = states[rc.key] ?? "pending";
            return (
              <li key={rc.key} className="rc-card" data-testid={`rc-card-${rc.key}`}>
                <div className="rc-card-h">
                  <span className={`rc-sev sev-${severityBucket(rc.severity_avg)}`} />
                  <span className="rc-comp">{rc.component}</span>
                  <span className="rc-key mono">{rc.key}</span>
                </div>
                <p className="rc-hyp">{rc.hypothesis}</p>
                <dl className="rc-metrics">
                  <div><dt>위험</dt><dd className="mono">{won(rc.revenue_at_risk_krw)}</dd></div>
                  <div><dt>회수</dt><dd className="mono">{won(rc.projected_recoverable_krw)}</dd></div>
                  <div><dt>빈도</dt><dd className="mono">{rc.frequency}</dd></div>
                  <div><dt>confidence</dt><dd className="mono">{rc.confidence_avg}</dd></div>
                </dl>

                {state === "pending" ? (
                  <div className="rc-actions">
                    <button type="button" className="rc-approve" disabled={busy} onClick={() => approveOne(rc.key)}>
                      승인
                    </button>
                    <button type="button" className="rc-reject" disabled={busy} onClick={() => rejectOne(rc.key)}>
                      반려
                    </button>
                  </div>
                ) : (
                  <p className="rc-state mono">{state === "dispatched" ? "dispatched · 발행됨" : "rejected · 반려됨"}</p>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="rc-loading mono">루트원인 집계 불러오는 중…</div>
      )}
    </section>
  );
}
