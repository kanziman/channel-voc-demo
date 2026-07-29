import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { OntologyGraphTab, mergeSubgraph } from "./OntologyGraphTab";
import type { SubgraphResponse } from "../api/graph";

// Records tap/node handlers registered via the `cy` callback so tests can fire a
// canvas node tap without a real cytoscape instance.
const tapHandlers: Array<(evt: { target: { id: () => string } }) => void> = [];
vi.mock("react-cytoscapejs", () => ({
  default: ({ elements, cy }: { elements: unknown[]; cy?: (c: unknown) => void }) => {
    if (cy) {
      cy({
        off: () => {},
        on: (_ev: string, _sel: string, h: (evt: { target: { id: () => string } }) => void) =>
          tapHandlers.push(h),
      });
    }
    return (
      <div data-testid="cytoscape" data-count={Array.isArray(elements) ? elements.length : 0} />
    );
  },
}));

const SNAP: SubgraphResponse = {
  nodes: [
    { id: "rc::rc_billing", type: "RootCause", label: "billing" },
    { id: "comp::billing", type: "Component", label: "billing" },
  ],
  edges: [{ source: "comp::billing", target: "rc::rc_billing", type: "CAUSED_BY" }],
  center: "rc::rc_billing",
};

const EXPANDED: SubgraphResponse = {
  nodes: [
    { id: "comp::billing", type: "Component", label: "billing" }, // dup with SNAP
    { id: "conv::conv_00001", type: "Conversation", label: "conv_00001" }, // new
  ],
  edges: [
    { source: "comp::billing", target: "rc::rc_billing", type: "CAUSED_BY" }, // dup
    { source: "conv::conv_00001", target: "comp::billing", type: "MENTIONS" }, // new
  ],
  center: "comp::billing",
};

afterEach(() => {
  tapHandlers.length = 0;
  vi.restoreAllMocks();
});

describe("mergeSubgraph", () => {
  it("should union nodes by id and edges by source→target:type (dedupe)", () => {
    const merged = mergeSubgraph(SNAP, EXPANDED);
    expect(merged.nodes.map((n) => n.id).sort()).toEqual([
      "comp::billing",
      "conv::conv_00001",
      "rc::rc_billing",
    ]);
    expect(merged.edges).toHaveLength(2); // one duplicate CAUSED_BY collapsed
  });

  it("should keep both distinct nodes/edges and prefer b.center", () => {
    const merged = mergeSubgraph(SNAP, EXPANDED);
    expect(merged.center).toBe("comp::billing");
    expect(merged.edges.some((e) => e.type === "MENTIONS")).toBe(true);
  });
});

describe("OntologyGraphTab", () => {
  it("should load the default snapshot on mount (getSubgraphFn with no args)", async () => {
    const getSubgraphFn = vi.fn().mockResolvedValue(SNAP);
    render(<OntologyGraphTab getSubgraphFn={getSubgraphFn} />);

    await waitFor(() => expect(getSubgraphFn).toHaveBeenCalledTimes(1));
    expect(getSubgraphFn).toHaveBeenCalledWith();
    await waitFor(() =>
      expect(screen.getByTestId("cytoscape")).toHaveAttribute("data-count", "3"),
    );
  });

  it("should expand a node with {expand:id, hops:1} and merge the result on node click", async () => {
    const getSubgraphFn = vi
      .fn()
      .mockResolvedValueOnce(SNAP)
      .mockResolvedValueOnce(EXPANDED);
    render(<OntologyGraphTab getSubgraphFn={getSubgraphFn} />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /comp::billing/ })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /comp::billing/ }));

    await waitFor(() =>
      expect(getSubgraphFn).toHaveBeenLastCalledWith({ expand: "comp::billing", hops: 1 }),
    );
    // merged: 3 nodes + 2 edges = 5 elements
    await waitFor(() =>
      expect(screen.getByTestId("cytoscape")).toHaveAttribute("data-count", "5"),
    );
  });

  it("should use hops:2 when the 2-hop toggle is selected", async () => {
    const getSubgraphFn = vi
      .fn()
      .mockResolvedValueOnce(SNAP)
      .mockResolvedValueOnce(EXPANDED);
    render(<OntologyGraphTab getSubgraphFn={getSubgraphFn} />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /comp::billing/ })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /2-hop/ }));
    fireEvent.click(screen.getByRole("button", { name: /comp::billing/ }));

    await waitFor(() =>
      expect(getSubgraphFn).toHaveBeenLastCalledWith({ expand: "comp::billing", hops: 2 }),
    );
  });

  it("should expand from a cytoscape canvas node tap (not only the node list)", async () => {
    const getSubgraphFn = vi
      .fn()
      .mockResolvedValueOnce(SNAP)
      .mockResolvedValueOnce(EXPANDED);
    render(<OntologyGraphTab getSubgraphFn={getSubgraphFn} />);

    await waitFor(() => expect(screen.getByTestId("cytoscape")).toBeInTheDocument());
    // a tap/node handler was bound to the canvas
    expect(tapHandlers.length).toBeGreaterThan(0);

    // firing it with a node id expands like a real canvas click
    tapHandlers[tapHandlers.length - 1]({ target: { id: () => "comp::billing" } });

    await waitFor(() =>
      expect(getSubgraphFn).toHaveBeenLastCalledWith({ expand: "comp::billing", hops: 1 }),
    );
  });

  it("should show an error state when the initial load fails", async () => {
    const getSubgraphFn = vi.fn().mockRejectedValue(new Error("network"));
    render(<OntologyGraphTab getSubgraphFn={getSubgraphFn} />);

    await waitFor(() => expect(screen.getByTestId("ontology-error")).toBeInTheDocument());
  });
});
