import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApprovalCard } from "./ApprovalCard";
import type { DispatchResponse, InterruptPayload } from "../api/agent";

const PAYLOAD: InterruptPayload = {
  message: "Approve which root-cause issues to dispatch?",
  candidates: [
    {
      root_cause_key: "rc_billing",
      component: "billing",
      title: "billing 결제 실패 급증",
      revenue_at_risk_krw: 6484500,
      confidence: 0.82,
      cited_conv_ids: ["conv_00001", "conv_00002"],
    },
  ],
};

const DISPATCHED: DispatchResponse = {
  thread_id: "agent-abc123",
  status: "dispatched",
  dispatched: [
    {
      key: "act_rc_billing",
      root_cause_key: "rc_billing",
      title: "[VOC] billing 결제 실패 급증",
      url: "https://github.com/x/y/issues/40",
      status: "dispatched",
      revenue_at_risk_krw: 6484500,
      cited: ["conv_00001"],
    },
  ],
};

const REJECTED: DispatchResponse = {
  thread_id: "agent-abc123",
  status: "rejected",
  dispatched: [],
};

afterEach(() => vi.restoreAllMocks());

describe("ApprovalCard", () => {
  it("should render nothing when interruptPayload is null", () => {
    const { container } = render(
      <ApprovalCard interruptPayload={null} threadId="agent-abc123" dispatchFn={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("should show action, target, thread_id(mono) and 회수손실(₩ mono) when payload present", () => {
    render(
      <ApprovalCard interruptPayload={PAYLOAD} threadId="agent-abc123" dispatchFn={vi.fn()} />,
    );

    expect(screen.getByText(/billing 결제 실패 급증/)).toBeInTheDocument(); // action
    expect(screen.getByText("billing")).toBeInTheDocument(); // target/component
    expect(screen.getByText("agent-abc123")).toHaveClass("mono"); // thread_id mono
    const risk = screen.getByText(/₩6,484,500/);
    expect(risk).toHaveClass("mono"); // 회수손실 mono
  });

  it("should dispatch approve and render the opened issue link/provenance on 승인", async () => {
    const dispatchFn = vi.fn().mockResolvedValue(DISPATCHED);
    render(
      <ApprovalCard interruptPayload={PAYLOAD} threadId="agent-abc123" dispatchFn={dispatchFn} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /승인/ }));

    await waitFor(() =>
      expect(dispatchFn).toHaveBeenCalledWith({ thread_id: "agent-abc123", decision: "approve" }),
    );
    const link = await screen.findByRole("link", { name: /issues\/40/ });
    expect(link).toHaveAttribute("href", "https://github.com/x/y/issues/40");
    expect(screen.getByText("act_rc_billing")).toHaveClass("mono"); // provenance key mono
  });

  it("should dispatch reject and render the rejected state on 반려", async () => {
    const dispatchFn = vi.fn().mockResolvedValue(REJECTED);
    render(
      <ApprovalCard interruptPayload={PAYLOAD} threadId="agent-abc123" dispatchFn={dispatchFn} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /반려/ }));

    await waitFor(() =>
      expect(dispatchFn).toHaveBeenCalledWith({ thread_id: "agent-abc123", decision: "reject" }),
    );
    expect(await screen.findByText(/반려됨/)).toBeInTheDocument();
  });

  it("should call onResolved with the dispatch response after resolving", async () => {
    const dispatchFn = vi.fn().mockResolvedValue(DISPATCHED);
    const onResolved = vi.fn();
    render(
      <ApprovalCard
        interruptPayload={PAYLOAD}
        threadId="agent-abc123"
        dispatchFn={dispatchFn}
        onResolved={onResolved}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /승인/ }));

    await waitFor(() => expect(onResolved).toHaveBeenCalledWith(DISPATCHED));
  });

  it("should disable the buttons while dispatching", async () => {
    let resolve!: (r: DispatchResponse) => void;
    const dispatchFn = vi.fn().mockReturnValue(
      new Promise<DispatchResponse>((r) => {
        resolve = r;
      }),
    );
    render(
      <ApprovalCard interruptPayload={PAYLOAD} threadId="agent-abc123" dispatchFn={dispatchFn} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /승인/ }));

    await waitFor(() => expect(screen.getByRole("button", { name: /승인/ })).toBeDisabled());
    expect(screen.getByRole("button", { name: /반려/ })).toBeDisabled();

    resolve(DISPATCHED);
  });

  it("should dispatch only once when 승인 is clicked twice in a row", async () => {
    let resolve!: (r: DispatchResponse) => void;
    const dispatchFn = vi.fn().mockReturnValue(
      new Promise<DispatchResponse>((r) => {
        resolve = r;
      }),
    );
    render(
      <ApprovalCard interruptPayload={PAYLOAD} threadId="agent-abc123" dispatchFn={dispatchFn} />,
    );

    const approve = screen.getByRole("button", { name: /승인/ });
    fireEvent.click(approve);
    fireEvent.click(approve); // rapid second click before re-render

    expect(dispatchFn).toHaveBeenCalledTimes(1);
    resolve(DISPATCHED);
  });

  it("should show an error and keep the card when dispatch fails", async () => {
    const dispatchFn = vi.fn().mockRejectedValue(new Error("boom"));
    render(
      <ApprovalCard interruptPayload={PAYLOAD} threadId="agent-abc123" dispatchFn={dispatchFn} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /승인/ }));

    await waitFor(() => expect(screen.getByText(/오류|boom/i)).toBeInTheDocument());
    // card still present (action visible)
    expect(screen.getByText(/billing 결제 실패 급증/)).toBeInTheDocument();
  });
});
