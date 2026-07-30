import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HybridSearchTab, toColumns } from "./HybridSearchTab";
import type { HybridResult, HybridSearchResponse } from "../api/search";

const RESULTS: HybridResult[] = [
  { id: "conv_a", dense: 0.9, sparse: 0.2, in_graph: true, rrf: 0.031, arms: ["dense", "sparse", "graph"] },
  { id: "conv_b", dense: 0.4, sparse: null, in_graph: false, rrf: 0.016, arms: ["dense"] },
  { id: "conv_c", dense: null, sparse: 0.7, in_graph: true, rrf: 0.022, arms: ["sparse", "graph"] },
];

const RESP: HybridSearchResponse = {
  query: "결제 실패",
  top_component: "billing",
  counts: { dense: 2, sparse: 2, graph: 2 },
  results: RESULTS,
};

afterEach(() => vi.restoreAllMocks());

describe("toColumns", () => {
  it("should split results into dense/sparse/graph arms by their score/flag", () => {
    const cols = toColumns(RESULTS);
    expect(cols.dense.map((r) => r.id)).toEqual(["conv_a", "conv_b"]); // dense != null
    expect(cols.sparse.map((r) => r.id)).toEqual(["conv_c", "conv_a"]); // sparse != null, desc
    expect(cols.graph.map((r) => r.id).sort()).toEqual(["conv_a", "conv_c"]); // in_graph
  });

  it("should sort each arm column and rrf fusion descending", () => {
    const cols = toColumns(RESULTS);
    expect(cols.dense.map((r) => r.dense)).toEqual([0.9, 0.4]); // dense desc
    expect(cols.rrf.map((r) => r.id)).toEqual(["conv_a", "conv_c", "conv_b"]); // rrf desc
  });
});

describe("HybridSearchTab", () => {
  it("should call searchFn with the query and render the three arm columns + RRF on submit", async () => {
    const searchFn = vi.fn().mockResolvedValue(RESP);
    render(<HybridSearchTab searchFn={searchFn} />);

    const input = screen.getByPlaceholderText(/order status|검색|서치|query/i);
    fireEvent.change(input, { target: { value: "결제 실패" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() =>
      expect(searchFn).toHaveBeenCalledWith(expect.objectContaining({ query: "결제 실패" })),
    );
    await waitFor(() => expect(screen.getByTestId("col-dense")).toBeInTheDocument());
    expect(screen.getByTestId("col-sparse")).toBeInTheDocument();
    expect(screen.getByTestId("col-graph")).toBeInTheDocument();
    expect(screen.getByTestId("col-rrf")).toBeInTheDocument();

    // dense column holds conv_a (dense hit), rrf column holds all three
    expect(within(screen.getByTestId("col-dense")).getByText("conv_a")).toBeInTheDocument();
    expect(within(screen.getByTestId("col-rrf")).getByText("conv_b")).toBeInTheDocument();
  });

  it("should render result ids and scores in mono", async () => {
    const searchFn = vi.fn().mockResolvedValue(RESP);
    render(<HybridSearchTab searchFn={searchFn} />);

    const input = screen.getByPlaceholderText(/order status|검색|서치|query/i);
    fireEvent.change(input, { target: { value: "x" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(screen.getByTestId("col-dense")).toBeInTheDocument());
    const dense = screen.getByTestId("col-dense");
    expect(within(dense).getByText("conv_a")).toHaveClass("mono");
    expect(within(dense).getByText("0.9")).toHaveClass("mono");

    // the RRF fusion column renders scores in mono too
    const rrf = screen.getByTestId("col-rrf");
    expect(within(rrf).getByText("0.031")).toHaveClass("mono");
  });

  it("should ignore an empty/whitespace query", () => {
    const searchFn = vi.fn().mockResolvedValue(RESP);
    render(<HybridSearchTab searchFn={searchFn} />);

    const input = screen.getByPlaceholderText(/order status|검색|서치|query/i);
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.submit(input.closest("form")!);

    expect(searchFn).not.toHaveBeenCalled();
  });

  it("should show an error state when the search fails", async () => {
    const searchFn = vi.fn().mockRejectedValue(new Error("boom"));
    render(<HybridSearchTab searchFn={searchFn} />);

    const input = screen.getByPlaceholderText(/order status|검색|서치|query/i);
    fireEvent.change(input, { target: { value: "x" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(screen.getByTestId("search-error")).toBeInTheDocument());
  });
});
