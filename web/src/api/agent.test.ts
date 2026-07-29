import { afterEach, describe, expect, it, vi } from "vitest";
import { getRootcauses, postDispatch, postRun } from "./agent";
import type { DispatchResponse } from "./agent";

const OK: DispatchResponse = {
  thread_id: "agent-abc123",
  status: "dispatched",
  dispatched: [
    {
      key: "act_rc_billing",
      root_cause_key: "rc_billing",
      title: "[VOC] billing 결제 실패",
      url: "https://github.com/x/y/issues/40",
      status: "dispatched",
      revenue_at_risk_krw: 6484500,
      cited: ["conv_00001"],
    },
  ],
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

describe("postDispatch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("should POST /api/agent/dispatch with {thread_id, decision}", async () => {
    const fetchMock = mockFetch(OK);
    vi.stubGlobal("fetch", fetchMock);

    await postDispatch({ thread_id: "agent-abc123", decision: "approve" });

    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/agent\/dispatch$/);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ thread_id: "agent-abc123", decision: "approve" });
  });

  it("should return the parsed DispatchResponse when res.ok", async () => {
    vi.stubGlobal("fetch", mockFetch(OK));
    const res = await postDispatch({ thread_id: "agent-abc123", decision: "approve" });
    expect(res).toEqual(OK);
  });

  it("should throw the {error} envelope message when res.ok is false", async () => {
    vi.stubGlobal("fetch", mockFetch({ error: "unknown or expired thread_id" }, { ok: false, status: 404 }));
    await expect(
      postDispatch({ thread_id: "nope", decision: "approve" }),
    ).rejects.toThrow(/unknown or expired thread_id/);
  });

  it("should fall back to statusText when the error body is not JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not json");
      },
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      postDispatch({ thread_id: "agent-abc123", decision: "approve" }),
    ).rejects.toThrow(/Internal Server Error/);
  });
});

describe("getRootcauses", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("should GET /api/agent/rootcauses and return {rootcauses}", async () => {
    const body = { rootcauses: [{ key: "rc_billing", component: "billing" }] };
    const fetchMock = mockFetch(body);
    vi.stubGlobal("fetch", fetchMock);

    const res = await getRootcauses();

    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/agent\/rootcauses$/);
    expect(opts?.method ?? "GET").toBe("GET");
    expect(res).toEqual(body);
  });
});

describe("postRun", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("should POST /api/agent/run with {live} and return the run response", async () => {
    const body = { thread_id: "agent-xyz", interrupt: { message: "m", candidates: [] }, dispatched: null };
    const fetchMock = mockFetch(body);
    vi.stubGlobal("fetch", fetchMock);

    const res = await postRun(true);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/agent\/run$/);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ live: true });
    expect(res).toEqual(body);
  });
});
