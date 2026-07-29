import { afterEach, describe, expect, it, vi } from "vitest";
import { getSubgraph } from "./graph";
import type { SubgraphResponse } from "./graph";

const SUB: SubgraphResponse = {
  nodes: [
    { id: "rc::rc_billing", type: "RootCause", label: "billing" },
    { id: "comp::billing", type: "Component", label: "billing" },
  ],
  edges: [{ source: "comp::billing", target: "rc::rc_billing", type: "CAUSED_BY" }],
  center: "rc::rc_billing",
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

describe("getSubgraph", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("should GET /api/graph/subgraph with no query when called without params", async () => {
    const fetchMock = mockFetch(SUB);
    vi.stubGlobal("fetch", fetchMock);

    await getSubgraph();

    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/graph\/subgraph$/);
    expect(opts?.method ?? "GET").toBe("GET");
  });

  it("should include expand and hops in the query string when provided", async () => {
    const fetchMock = mockFetch(SUB);
    vi.stubGlobal("fetch", fetchMock);

    await getSubgraph({ expand: "rc::rc_billing", hops: 2 });

    const [url] = fetchMock.mock.calls[0];
    const u = new URL(String(url), "http://x");
    expect(u.searchParams.get("expand")).toBe("rc::rc_billing");
    expect(u.searchParams.get("hops")).toBe("2");
  });

  it("should return the parsed SubgraphResponse when res.ok", async () => {
    vi.stubGlobal("fetch", mockFetch(SUB));
    const res = await getSubgraph();
    expect(res).toEqual(SUB);
  });

  it("should throw the {error} envelope message when res.ok is false", async () => {
    vi.stubGlobal("fetch", mockFetch({ error: "bad expand prefix" }, { ok: false, status: 400 }));
    await expect(getSubgraph({ expand: "nope::x" })).rejects.toThrow(/bad expand prefix/);
  });
});
