import { afterEach, describe, expect, it, vi } from "vitest";
import { postSearch } from "./search";
import type { HybridSearchResponse } from "./search";

const OK: HybridSearchResponse = {
  query: "결제 실패",
  top_component: "billing",
  counts: { dense: 6, sparse: 6, graph: 4 },
  results: [
    { id: "conv_00001", dense: 0.9, sparse: 0.4, in_graph: true, rrf: 0.031, arms: ["dense", "sparse", "graph"] },
    { id: "conv_00002", dense: 0.5, sparse: null, in_graph: false, rrf: 0.016, arms: ["dense"] },
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

describe("postSearch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("should POST /api/search/hybrid with {query, k}", async () => {
    const fetchMock = mockFetch(OK);
    vi.stubGlobal("fetch", fetchMock);

    await postSearch({ query: "결제 실패", k: 8 });

    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/search\/hybrid$/);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toMatchObject({ query: "결제 실패", k: 8 });
  });

  it("should return the parsed HybridSearchResponse when res.ok", async () => {
    vi.stubGlobal("fetch", mockFetch(OK));
    const res = await postSearch({ query: "결제 실패" });
    expect(res).toEqual(OK);
  });

  it("should throw the {error} envelope message when res.ok is false", async () => {
    vi.stubGlobal("fetch", mockFetch({ error: "empty query" }, { ok: false, status: 400 }));
    await expect(postSearch({ query: "" })).rejects.toThrow(/empty query/);
  });
});
