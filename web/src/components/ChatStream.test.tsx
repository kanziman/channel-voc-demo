import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ChatStream } from "./ChatStream";
import type { ChatResponse } from "../api/chat";

function makeResponse(over: Partial<ChatResponse> = {}): ChatResponse {
  return {
    answer: "위험 ₩6,484,500, 회수가능 ₩3,306,600, confidence 0.82",
    arms: ["dense", "sparse", "graph"],
    subgraph_ref: { top_component: "ORDER" },
    confidence: 0.82,
    gate: "answer",
    related_questions: ["ORDER 근거 대화 보여줘"],
    interrupt_payload: null,
    evidence: [],
    ...over,
  };
}

/** Type a question into the composer and submit it. */
function ask(question: string) {
  const input = screen.getByPlaceholderText(/질문/);
  fireEvent.change(input, { target: { value: question } });
  fireEvent.submit(input.closest("form")!);
  return input as HTMLInputElement;
}

/** Map of arm key → data-state, for the most recent (active) trace. */
function armStates(): Record<string, string> {
  const arms = document.querySelectorAll("[data-arm]");
  const out: Record<string, string> = {};
  arms.forEach((el) => {
    out[el.getAttribute("data-arm")!] = el.getAttribute("data-state") ?? "";
  });
  return out;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("ChatStream", () => {
  it("should append the user message to the stream when a question is submitted", async () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse());
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("결제 실패 왜 이렇게 많아?");

    expect(screen.getByText("결제 실패 왜 이렇게 많아?")).toBeInTheDocument();
    expect(postChatFn).toHaveBeenCalledWith(
      expect.objectContaining({ message: "결제 실패 왜 이렇게 많아?" }),
    );
  });

  it("should clear the composer input after submit", () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse());
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    const input = ask("질문 하나");

    expect(input.value).toBe("");
  });

  it("should ignore submit when the input is empty or whitespace", () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse());
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("   ");

    expect(postChatFn).not.toHaveBeenCalled();
  });

  it("should light arms in D→S→G order when awaiting the answer", async () => {
    vi.useFakeTimers();
    let resolveResp!: (r: ChatResponse) => void;
    const postChatFn = vi.fn().mockReturnValue(
      new Promise<ChatResponse>((res) => {
        resolveResp = res;
      }),
    );
    render(<ChatStream postChatFn={postChatFn} armStepMs={100} />);

    ask("결제 실패 원인?");

    // D lights first.
    await act(async () => {
      vi.advanceTimersByTime(100);
    });
    expect(armStates().D).toBe("lit");
    expect(armStates().S).toBe("pending");
    expect(armStates().G).toBe("pending");

    // then S.
    await act(async () => {
      vi.advanceTimersByTime(100);
    });
    expect(armStates().S).toBe("lit");
    expect(armStates().G).toBe("pending");

    // then G.
    await act(async () => {
      vi.advanceTimersByTime(100);
    });
    expect(armStates().G).toBe("lit");

    await act(async () => {
      resolveResp(makeResponse());
    });
  });

  it("should render the bot answer only after all three arms have lit", async () => {
    vi.useFakeTimers();
    const answer = "위험 ₩6,484,500, 회수가능 ₩3,306,600, confidence 0.82";
    const postChatFn = vi.fn().mockResolvedValue(makeResponse({ answer }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={100} />);

    ask("결제 실패 원인?");

    // Before arms complete, the answer must not be shown.
    await act(async () => {
      vi.advanceTimersByTime(100);
    });
    expect(screen.queryByTestId("answer")).not.toBeInTheDocument();

    // Complete the arm sweep and flush the resolved response.
    await act(async () => {
      vi.advanceTimersByTime(200);
    });
    await act(async () => {
      await Promise.resolve();
    });

    // ₩ amounts render as mono spans (DESIGN.md), so the answer text is split
    // across nodes — assert on the container's full text content, not a single
    // text node.
    expect(screen.getByTestId("answer")).toHaveTextContent(answer);
  });

  it("should render response.answer verbatim (exact ₩ text, no client-side regeneration)", async () => {
    // Contains an id token (rc_order_gateway) that cite-drilldown linkifies, so the
    // content is split across nodes — assert the *content* is preserved verbatim.
    const answer = "루트원인 rc_order_gateway — 위험 ₩6,484,500, 회수가능 ₩3,306,600";
    const postChatFn = vi.fn().mockResolvedValue(makeResponse({ answer }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("ORDER 실패 원인?");

    await waitFor(() => expect(screen.getByTestId("answer")).toBeInTheDocument());
    expect(screen.getByTestId("answer")).toHaveTextContent(answer);
  });

  it("should mark arms present in response.arms as hit and absent ones as dim", async () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse({ arms: ["dense", "graph"] }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("ORDER 실패 원인?");

    await waitFor(() => expect(screen.getByTestId("answer")).toBeInTheDocument());

    const bot = screen.getByTestId("answer").closest("[data-role='bot']")!;
    const armsInBot = within(bot as HTMLElement).getAllByTestId(/arm-hit-/);
    const hitMap: Record<string, string> = {};
    armsInBot.forEach((el) => {
      hitMap[el.getAttribute("data-arm")!] = el.getAttribute("data-hit") ?? "";
    });
    expect(hitMap.D).toBe("true"); // dense
    expect(hitMap.S).toBe("false"); // sparse absent → dim
    expect(hitMap.G).toBe("true"); // graph
  });

  it("should still complete the trace and render the refuse answer when arms is empty", async () => {
    const refuse = "VOC 지식그래프에 근거가 없어 답할 수 없어요.";
    const postChatFn = vi.fn().mockResolvedValue(
      makeResponse({ answer: refuse, arms: [], gate: "refuse", confidence: 0 }),
    );
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("우주의 끝은?");

    await waitFor(() => expect(screen.getByText(refuse)).toBeInTheDocument());
  });

  it("should append an error message and not crash when postChatFn rejects", async () => {
    const postChatFn = vi.fn().mockRejectedValue(new Error("boom in retriever"));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("결제 실패 원인?");

    await waitFor(() =>
      expect(screen.getByText(/오류|error|boom/i)).toBeInTheDocument(),
    );
    // the user message is still present → no crash / unmount
    expect(screen.getByText("결제 실패 원인?")).toBeInTheDocument();
  });

  it("should render an rc_ id in the answer as a clickable cite link", async () => {
    const answer = "루트원인 rc_ORDER 를 확인하세요";
    const postChatFn = vi.fn().mockResolvedValue(makeResponse({ answer }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("ORDER 실패 원인?");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "rc_ORDER" })).toBeInTheDocument(),
    );
  });

  it("should auto-submit the follow-up question when a cite link is clicked", async () => {
    const postChatFn = vi
      .fn()
      .mockResolvedValueOnce(makeResponse({ answer: "루트원인 rc_ORDER 확인" }))
      .mockResolvedValueOnce(makeResponse({ answer: "rc_ORDER 근거 대화 6건" }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("ORDER 실패 원인?");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "rc_ORDER" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "rc_ORDER" }));

    // second call dispatched with the follow-up question
    await waitFor(() => expect(postChatFn).toHaveBeenCalledTimes(2));
    expect(postChatFn).toHaveBeenLastCalledWith(
      expect.objectContaining({ message: "rc_ORDER 근거 대화 보여줘" }),
    );
    // and that follow-up shows up as a user turn
    expect(screen.getByText("rc_ORDER 근거 대화 보여줘")).toBeInTheDocument();
  });

  it("should disable cite links and ignore clicks while a question is in flight", async () => {
    const postChatFn = vi
      .fn()
      .mockResolvedValueOnce(makeResponse({ answer: "루트원인 rc_ORDER 확인" }))
      .mockReturnValueOnce(new Promise<ChatResponse>(() => {})); // second turn never resolves
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("ORDER 실패 원인?");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "rc_ORDER" })).toBeInTheDocument(),
    );

    // start a second question → stream stays tracing (pending promise)
    ask("다른 질문");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "rc_ORDER" })).toBeDisabled(),
    );

    // clicking the now-disabled cite must not dispatch a third call
    fireEvent.click(screen.getByRole("button", { name: "rc_ORDER" }));
    expect(postChatFn).toHaveBeenCalledTimes(2);
  });

  it("should show seed chips before any question (cold-start non-empty)", () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse());
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    expect(screen.getByRole("button", { name: "손실 Top3 루트원인은?" })).toBeInTheDocument();
  });

  it("should replace chips with response.related_questions after an answer", async () => {
    const postChatFn = vi
      .fn()
      .mockResolvedValue(makeResponse({ related_questions: ["auth 위험액은 얼마야?"] }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("auth 실패 원인?");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "auth 위험액은 얼마야?" })).toBeInTheDocument(),
    );
    // seed chip replaced
    expect(screen.queryByRole("button", { name: "손실 Top3 루트원인은?" })).not.toBeInTheDocument();
  });

  it("should auto-submit the question when a related chip is clicked", async () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse());
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    fireEvent.click(screen.getByRole("button", { name: "가장 심각한 컴포넌트는?" }));

    await waitFor(() => expect(postChatFn).toHaveBeenCalledTimes(1));
    expect(postChatFn).toHaveBeenCalledWith(
      expect.objectContaining({ message: "가장 심각한 컴포넌트는?" }),
    );
    // let the answer land so seed chips are replaced, leaving only the user turn
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "ORDER 근거 대화 보여줘" })).toBeInTheDocument(),
    );
    const userTurn = screen.getByText("가장 심각한 컴포넌트는?");
    expect(userTurn.closest("[data-role='user']")).not.toBeNull();
  });

  it("should disable related chips and ignore clicks while a question is in flight", async () => {
    const postChatFn = vi.fn().mockReturnValueOnce(new Promise<ChatResponse>(() => {}));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("무언가 질문"); // enters tracing; pending promise keeps it there
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "손실 Top3 루트원인은?" })).toBeDisabled(),
    );

    fireEvent.click(screen.getByRole("button", { name: "손실 Top3 루트원인은?" }));
    expect(postChatFn).toHaveBeenCalledTimes(1); // chip click ignored
  });

  it("should fall back to seed chips when response.related_questions is empty", async () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse({ related_questions: [] }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("auth 실패 원인?");

    await waitFor(() => expect(screen.getByTestId("answer")).toBeInTheDocument());
    // empty related_questions → UI must not go empty
    expect(screen.getByRole("button", { name: "손실 Top3 루트원인은?" })).toBeInTheDocument();
  });

  it("should show the confidence gate banner after a refuse answer", async () => {
    const postChatFn = vi.fn().mockResolvedValue(
      makeResponse({
        answer: "근거가 없어 답할 수 없어요.",
        arms: [],
        gate: "refuse",
        confidence: 0,
      }),
    );
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("우주의 끝은?");

    await waitFor(() =>
      expect(screen.getByTestId("confidence-gate")).toHaveAttribute("data-gate", "refuse"),
    );
  });

  it("should show the ⚠ low-confidence banner with confidence after a low_confidence answer", async () => {
    const postChatFn = vi.fn().mockResolvedValue(
      makeResponse({
        answer: "⚠ 확신이 낮아요 …",
        gate: "low_confidence",
        confidence: 0.32,
      }),
    );
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("auth 실패 원인?");

    await waitFor(() =>
      expect(screen.getByTestId("confidence-gate")).toHaveAttribute("data-gate", "low_confidence"),
    );
    expect(screen.getByText("0.32")).toHaveClass("mono");
  });

  it("should not show a gate banner after a normal (answer) response", async () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse({ gate: "answer" }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("auth 실패 원인?");

    await waitFor(() => expect(screen.getByTestId("answer")).toBeInTheDocument());
    expect(screen.queryByTestId("confidence-gate")).not.toBeInTheDocument();
  });

  it("should replace (not duplicate) the composer chips when a gate banner is shown", async () => {
    const postChatFn = vi.fn().mockResolvedValue(
      makeResponse({ gate: "refuse", arms: [], confidence: 0, related_questions: ["auth 위험액은?"] }),
    );
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("우주의 끝은?");

    await waitFor(() => expect(screen.getByTestId("confidence-gate")).toBeInTheDocument());
    // exactly one chip with that text — the gate replaces the composer chips, no dup
    expect(screen.getAllByRole("button", { name: "auth 위험액은?" })).toHaveLength(1);
  });

  it("should clear the gate banner once a later answer turn arrives", async () => {
    const postChatFn = vi
      .fn()
      .mockResolvedValueOnce(makeResponse({ gate: "refuse", arms: [], confidence: 0 }))
      .mockResolvedValueOnce(makeResponse({ gate: "answer" }));
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} />);

    ask("우주의 끝은?");
    await waitFor(() => expect(screen.getByTestId("confidence-gate")).toBeInTheDocument());

    ask("auth 실패 원인?");
    await waitFor(() => expect(screen.queryByTestId("confidence-gate")).not.toBeInTheDocument());
  });

  // ── App wire-up seams (#44) ────────────────────────────────────────────────
  it("should send thread_id in the chat request when threadId prop is set", async () => {
    const postChatFn = vi.fn().mockResolvedValue(makeResponse());
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} threadId="t_abc123" />);

    ask("ORDER 실패 원인?");

    await waitFor(() => expect(postChatFn).toHaveBeenCalledTimes(1));
    expect(postChatFn).toHaveBeenCalledWith(
      expect.objectContaining({ message: "ORDER 실패 원인?", thread_id: "t_abc123" }),
    );
  });

  it("should invoke onResponse with the landed response when an answer arrives", async () => {
    const resp = makeResponse({ subgraph_ref: { top_component: "ORDER", root_cause_key: "rc_ORDER" } });
    const postChatFn = vi.fn().mockResolvedValue(resp);
    const onResponse = vi.fn();
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} onResponse={onResponse} />);

    ask("ORDER 실패 원인?");

    await waitFor(() => expect(onResponse).toHaveBeenCalledTimes(1));
    expect(onResponse).toHaveBeenCalledWith(resp);
  });

  it("should not invoke onResponse when postChatFn rejects", async () => {
    const postChatFn = vi.fn().mockRejectedValue(new Error("boom"));
    const onResponse = vi.fn();
    render(<ChatStream postChatFn={postChatFn} armStepMs={0} onResponse={onResponse} />);

    ask("ORDER 실패 원인?");

    await waitFor(() => expect(screen.getByText(/오류|boom/i)).toBeInTheDocument());
    expect(onResponse).not.toHaveBeenCalled();
  });
});
