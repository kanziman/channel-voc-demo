import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

// EvidencePanel + OntologyGraphTab draw on cytoscape (canvas) — stub it so jsdom
// can mount them. Only the element count is surfaced.
vi.mock("react-cytoscapejs", () => ({
  default: ({ elements }: { elements: unknown[] }) => (
    <div data-testid="cytoscape" data-count={Array.isArray(elements) ? elements.length : 0} />
  ),
}));

import { App } from "./App";
import type { AppDeps } from "./App";
import type { ChatResponse } from "./api/chat";
import type { SubgraphResponse } from "./api/graph";

function makeChat(over: Partial<ChatResponse> = {}): ChatResponse {
  return {
    answer: "위험 ₩6,484,500, 회수가능 ₩3,306,600, confidence 0.82",
    arms: ["dense", "sparse", "graph"],
    subgraph_ref: { top_component: "ORDER", root_cause_key: "rc_ORDER" },
    confidence: 0.82,
    gate: "answer",
    related_questions: ["ORDER 근거 대화 보여줘"],
    interrupt_payload: null,
    ...over,
  };
}

const SNAP: SubgraphResponse = {
  nodes: [
    { id: "rc::rc_ORDER", type: "RootCause", label: "ORDER" },
    { id: "comp::ORDER", type: "Component", label: "ORDER" },
  ],
  edges: [{ source: "comp::ORDER", target: "rc::rc_ORDER", type: "CAUSED_BY" }],
  center: "rc::rc_ORDER",
};

const INTERRUPT = {
  message: "루트원인 2건에 대해 GitHub 이슈를 발행할까요?",
  candidates: [
    { root_cause_key: "rc_ORDER", component: "ORDER", title: "주문 실패 급증", revenue_at_risk_krw: 6484500 },
  ],
};

function makeDeps(over: Partial<AppDeps> = {}): AppDeps {
  return {
    postChatFn: vi.fn().mockResolvedValue(makeChat()),
    getSubgraphFn: vi.fn().mockResolvedValue(SNAP),
    dispatchFn: vi.fn().mockResolvedValue({ thread_id: "t", status: "rejected", dispatched: [] }),
    rootcausesFn: vi.fn().mockResolvedValue({ rootcauses: [] }),
    runFn: vi.fn().mockResolvedValue({ thread_id: "t", interrupt: null, dispatched: null }),
    searchFn: vi.fn().mockResolvedValue({ query: "", results: [] }),
    ...over,
  };
}

/** Type + submit a question into the copilot composer. */
function ask(question: string) {
  const input = screen.getByPlaceholderText(/질문/);
  fireEvent.change(input, { target: { value: question } });
  fireEvent.submit(input.closest("form")!);
}

afterEach(() => {
  vi.useRealTimers();
});

describe("App", () => {
  it("should render the copilot view by default", () => {
    render(<App deps={makeDeps()} armStepMs={0} />);

    expect(screen.getByPlaceholderText(/질문/)).toBeInTheDocument();
    expect(screen.getByTestId("evidence-placeholder")).toBeInTheDocument();
    // console tabs are not mounted in copilot view
    expect(screen.queryByTestId("search-tab")).not.toBeInTheDocument();
  });

  it("should render the session thread_id in the header (mono)", () => {
    render(<App deps={makeDeps()} armStepMs={0} initialThreadId="t_test01" />);

    const tid = screen.getByText("t_test01");
    expect(tid).toBeInTheDocument();
    expect(tid).toHaveClass("mono");
  });

  it("should pass the session thread_id into the chat request", async () => {
    const deps = makeDeps();
    render(<App deps={deps} armStepMs={0} initialThreadId="t_test01" />);

    ask("ORDER 실패 원인?");

    await waitFor(() => expect(deps.postChatFn).toHaveBeenCalledTimes(1));
    expect(deps.postChatFn).toHaveBeenCalledWith(
      expect.objectContaining({ message: "ORDER 실패 원인?", thread_id: "t_test01" }),
    );
  });

  it("should feed the latest response subgraph_ref into the evidence panel", async () => {
    const deps = makeDeps();
    render(<App deps={deps} armStepMs={0} />);

    ask("ORDER 실패 원인?");

    await waitFor(() =>
      expect(deps.getSubgraphFn).toHaveBeenCalledWith({ expand: "rc::rc_ORDER", hops: 1 }),
    );
  });

  it("should show the approval card when the latest response carries interrupt_payload", async () => {
    const deps = makeDeps({
      postChatFn: vi.fn().mockResolvedValue(makeChat({ interrupt_payload: INTERRUPT })),
    });
    render(<App deps={deps} armStepMs={0} />);

    ask("손실 Top 루트원인 조치해줘");

    await waitFor(() => expect(screen.getByTestId("approval-card")).toBeInTheDocument());
    expect(screen.getByText("주문 실패 급증")).toBeInTheDocument();
  });

  it("should not render the approval card when interrupt_payload is null", async () => {
    render(<App deps={makeDeps()} armStepMs={0} />);

    ask("ORDER 실패 원인?");

    await waitFor(() => expect(screen.getByTestId("cytoscape")).toBeInTheDocument());
    expect(screen.queryByTestId("approval-card")).not.toBeInTheDocument();
  });

  it("should switch to the console view when EvidencePanel '⤢ 탐색' is clicked", () => {
    render(<App deps={makeDeps()} armStepMs={0} />);

    fireEvent.click(screen.getByRole("button", { name: /탐색/ }));

    // console default tab (ontology) is mounted; copilot composer is gone
    expect(screen.queryByPlaceholderText(/질문/)).not.toBeInTheDocument();
    expect(screen.getByTestId("console-view")).toBeInTheDocument();
  });

  it("should default the console active tab to ontology", async () => {
    render(<App deps={makeDeps()} armStepMs={0} initialView="console" />);

    // ontology tab renders the cytoscape canvas once its subgraph loads; search/gate not yet
    await waitFor(() => expect(screen.getByTestId("cytoscape")).toBeInTheDocument());
    expect(screen.queryByTestId("search-tab")).not.toBeInTheDocument();
    expect(screen.queryByTestId("rootcause-gate-tab")).not.toBeInTheDocument();
  });

  it("should render three console tabs and switch the active tab on click", async () => {
    render(<App deps={makeDeps()} armStepMs={0} initialView="console" />);

    fireEvent.click(screen.getByRole("tab", { name: /하이브리드/ }));
    expect(screen.getByTestId("search-tab")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /승인/ }));
    await waitFor(() => expect(screen.getByTestId("rootcause-gate-tab")).toBeInTheDocument());
  });

  it("should return to the copilot view via the back control", () => {
    render(<App deps={makeDeps()} armStepMs={0} initialView="console" />);

    fireEvent.click(screen.getByRole("button", { name: /코파일럿/ }));

    expect(screen.getByPlaceholderText(/질문/)).toBeInTheDocument();
    expect(screen.queryByTestId("console-view")).not.toBeInTheDocument();
  });

  it("should not crash when a console tab fetch fn rejects", async () => {
    const deps = makeDeps({
      rootcausesFn: vi.fn().mockRejectedValue(new Error("neo4j down")),
    });
    render(<App deps={deps} armStepMs={0} initialView="console" initialTab="gate" />);

    await waitFor(() => expect(screen.getByTestId("rc-error")).toBeInTheDocument());
  });
});
