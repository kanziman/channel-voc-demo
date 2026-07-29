import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { RootCauseGateTab, severityBucket } from "./RootCauseGateTab";
import type { DispatchResponse, RootCause, RunResponse } from "../api/agent";

const RCS: RootCause[] = [
  {
    key: "rc_billing",
    component: "billing",
    frequency: 42,
    revenue_at_risk_krw: 6484500,
    projected_recoverable_krw: 3306600,
    severity_avg: 0.85,
    confidence_avg: 0.82,
    hypothesis: "결제 게이트웨이 타임아웃",
  },
  {
    key: "rc_shipping",
    component: "shipping",
    frequency: 17,
    revenue_at_risk_krw: 1200000,
    projected_recoverable_krw: 600000,
    severity_avg: 0.45,
    confidence_avg: 0.6,
    hypothesis: "배송 추적 지연",
  },
];

const RUN: RunResponse = {
  thread_id: "agent-xyz",
  interrupt: { message: "approve?", candidates: [] },
  dispatched: null,
};

const DISPATCHED: DispatchResponse = {
  thread_id: "agent-xyz",
  status: "dispatched",
  dispatched: [
    {
      key: "act_rc_billing",
      root_cause_key: "rc_billing",
      title: "[VOC] billing",
      url: "https://github.com/x/y/issues/50",
      status: "dispatched",
      revenue_at_risk_krw: 6484500,
      cited: [],
    },
  ],
};

const REJECTED: DispatchResponse = { thread_id: "agent-xyz", status: "rejected", dispatched: [] };

afterEach(() => vi.restoreAllMocks());

describe("severityBucket", () => {
  it("should map severity_avg to good/warning/serious/critical thresholds", () => {
    expect(severityBucket(0.85)).toBe("critical");
    expect(severityBucket(0.65)).toBe("serious");
    expect(severityBucket(0.45)).toBe("warning");
    expect(severityBucket(0.2)).toBe("good");
  });

  it("should place the exact threshold values in the higher bucket (>=)", () => {
    expect(severityBucket(0.8)).toBe("critical");
    expect(severityBucket(0.79)).toBe("serious");
    expect(severityBucket(0.6)).toBe("serious");
    expect(severityBucket(0.59)).toBe("warning");
    expect(severityBucket(0.4)).toBe("warning");
    expect(severityBucket(0.39)).toBe("good");
  });
});

describe("RootCauseGateTab", () => {
  function deps(over: Partial<{
    rootcausesFn: () => Promise<{ rootcauses: RootCause[] }>;
    runFn: () => Promise<RunResponse>;
    dispatchFn: (r: unknown) => Promise<DispatchResponse>;
  }> = {}) {
    return {
      rootcausesFn: over.rootcausesFn ?? vi.fn().mockResolvedValue({ rootcauses: RCS }),
      runFn: over.runFn ?? vi.fn().mockResolvedValue(RUN),
      dispatchFn: over.dispatchFn ?? vi.fn().mockResolvedValue(DISPATCHED),
    };
  }

  it("should load rootcauses on mount and render ₩risk/₩recoverable/frequency/confidence (mono)", async () => {
    const d = deps();
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-card-rc_billing")).toBeInTheDocument());
    const card = screen.getByTestId("rc-card-rc_billing");
    expect(within(card).getByText(/₩6,484,500/)).toHaveClass("mono"); // revenue at risk
    expect(within(card).getByText(/₩3,306,600/)).toHaveClass("mono"); // recoverable
    expect(within(card).getByText("42")).toHaveClass("mono"); // frequency
    expect(within(card).getByText("0.82")).toHaveClass("mono"); // confidence
  });

  it("should approve a card via run→dispatch({decision:[key]}) and mark it dispatched", async () => {
    const d = deps();
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-card-rc_billing")).toBeInTheDocument());
    const card = screen.getByTestId("rc-card-rc_billing");
    fireEvent.click(within(card).getByRole("button", { name: /승인/ }));

    await waitFor(() => expect(d.runFn).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(d.dispatchFn).toHaveBeenCalledWith({ thread_id: "agent-xyz", decision: ["rc_billing"] }),
    );
    await waitFor(() =>
      expect(within(screen.getByTestId("rc-card-rc_billing")).getByText(/dispatched|발행|issues\/50/)).toBeInTheDocument(),
    );
  });

  it("should bulk-approve via dispatch('approve')", async () => {
    const d = deps();
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-card-rc_billing")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /일괄 승인/ }));

    await waitFor(() =>
      expect(d.dispatchFn).toHaveBeenCalledWith({ thread_id: "agent-xyz", decision: "approve" }),
    );
  });

  it("should bulk-reject via dispatch('reject')", async () => {
    const d = deps({ dispatchFn: vi.fn().mockResolvedValue(REJECTED) });
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-card-rc_billing")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /일괄 반려/ }));

    await waitFor(() =>
      expect(d.dispatchFn).toHaveBeenCalledWith({ thread_id: "agent-xyz", decision: "reject" }),
    );
  });

  it("should reject only the clicked card via dispatch('reject') and leave others pending", async () => {
    const d = deps();
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-card-rc_billing")).toBeInTheDocument());
    const billing = screen.getByTestId("rc-card-rc_billing");
    fireEvent.click(within(billing).getByRole("button", { name: /반려/ }));

    await waitFor(() =>
      expect(d.dispatchFn).toHaveBeenCalledWith({ thread_id: "agent-xyz", decision: "reject" }),
    );
    await waitFor(() =>
      expect(within(screen.getByTestId("rc-card-rc_billing")).getByText(/반려됨|rejected/)).toBeInTheDocument(),
    );
    // the other card is untouched — still shows its approve action
    const shipping = screen.getByTestId("rc-card-rc_shipping");
    expect(within(shipping).getByRole("button", { name: /승인/ })).toBeInTheDocument();
  });

  it("should approve only the clicked card (decision:[key]) and keep the other pending", async () => {
    const d = deps();
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-card-rc_billing")).toBeInTheDocument());
    fireEvent.click(
      within(screen.getByTestId("rc-card-rc_billing")).getByRole("button", { name: /승인/ }),
    );

    await waitFor(() =>
      expect(d.dispatchFn).toHaveBeenCalledWith({ thread_id: "agent-xyz", decision: ["rc_billing"] }),
    );
    const shipping = screen.getByTestId("rc-card-rc_shipping");
    expect(within(shipping).getByRole("button", { name: /승인/ })).toBeInTheDocument(); // still pending
  });

  it("should show an action error and keep the card pending when dispatch fails", async () => {
    const d = deps({ dispatchFn: vi.fn().mockRejectedValue(new Error("expired thread")) });
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-card-rc_billing")).toBeInTheDocument());
    fireEvent.click(
      within(screen.getByTestId("rc-card-rc_billing")).getByRole("button", { name: /승인/ }),
    );

    await waitFor(() => expect(screen.getByTestId("rc-action-error")).toBeInTheDocument());
    // card stayed pending (approve button still present)
    expect(
      within(screen.getByTestId("rc-card-rc_billing")).getByRole("button", { name: /승인/ }),
    ).toBeInTheDocument();
  });

  it("should dispatch only once when 일괄 승인 is clicked twice in a row", async () => {
    let resolveRun!: (r: RunResponse) => void;
    const runFn = vi.fn().mockReturnValue(new Promise<RunResponse>((r) => (resolveRun = r)));
    const d = deps({ runFn });
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-card-rc_billing")).toBeInTheDocument());
    const bulkApprove = screen.getByRole("button", { name: /일괄 승인/ });
    fireEvent.click(bulkApprove);
    fireEvent.click(bulkApprove); // second click while busy

    expect(runFn).toHaveBeenCalledTimes(1);
    resolveRun(RUN);
  });

  it("should show an error state when the rootcauses load fails", async () => {
    const d = deps({ rootcausesFn: vi.fn().mockRejectedValue(new Error("network")) });
    render(<RootCauseGateTab {...d} />);

    await waitFor(() => expect(screen.getByTestId("rc-error")).toBeInTheDocument());
  });
});
