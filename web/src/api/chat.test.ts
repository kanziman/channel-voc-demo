import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { postChat } from "./chat";
import type { ChatResponse } from "./chat";

const OK_BODY: ChatResponse = {
  answer: "위험 ₩6,484,500, 회수가능 ₩3,306,600",
  arms: ["dense", "graph"],
  subgraph_ref: { top_component: "ORDER" },
  confidence: 0.82,
  gate: "answer",
  related_questions: ["ORDER 근거 대화 보여줘"],
  interrupt_payload: null,
};

function mockFetch(body: unknown, init?: { ok?: boolean; status?: number }) {
  const ok = init?.ok ?? true;
  return vi.fn().mockResolvedValue({
    ok,
    status: init?.status ?? (ok ? 200 : 500),
    statusText: ok ? "OK" : "Internal Server Error",
    json: async () => body,
  } as unknown as Response);
}

describe("postChat", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", mockFetch(OK_BODY));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("should POST to /api/chat with JSON body and return parsed ChatResponse when res.ok", async () => {
    const fetchMock = mockFetch(OK_BODY);
    vi.stubGlobal("fetch", fetchMock);

    const res = await postChat({ message: "결제 실패 왜 이렇게 많아?" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/chat$/);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toMatchObject({ message: "결제 실패 왜 이렇게 많아?" });
    expect(res).toEqual(OK_BODY);
  });

  it("should include thread_id in body when provided", async () => {
    const fetchMock = mockFetch(OK_BODY);
    vi.stubGlobal("fetch", fetchMock);

    await postChat({ message: "재개", thread_id: "th_123" });

    const [, opts] = fetchMock.mock.calls[0];
    expect(JSON.parse(opts.body)).toMatchObject({ message: "재개", thread_id: "th_123" });
  });

  it("should throw Error with {error} envelope message when res.ok is false", async () => {
    vi.stubGlobal("fetch", mockFetch({ error: "boom in retriever" }, { ok: false, status: 500 }));

    await expect(postChat({ message: "x" })).rejects.toThrow(/boom in retriever/);
  });

  it("should throw with statusText when error body is absent or unparseable", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => {
        throw new Error("not json");
      },
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(postChat({ message: "x" })).rejects.toThrow(/Bad Gateway/);
  });
});
