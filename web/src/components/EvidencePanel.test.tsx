import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import {
  EvidencePanel,
  graphStylesheet,
  toElements,
} from "./EvidencePanel";
import type { SubgraphResponse } from "../api/graph";

// react-cytoscapejs needs canvas layout that jsdom lacks — stub it and expose
// the element count so we can assert the panel drew the fetched subgraph.
vi.mock("react-cytoscapejs", () => ({
  default: ({ elements }: { elements: unknown[] }) => (
    <div data-testid="cytoscape" data-count={Array.isArray(elements) ? elements.length : 0} />
  ),
}));

const SUB: SubgraphResponse = {
  nodes: [
    { id: "rc::rc_billing", type: "RootCause", label: "billing" },
    { id: "comp::billing", type: "Component", label: "billing" },
    { id: "conv::conv_00001", type: "Conversation", label: "conv_00001" },
  ],
  edges: [
    { source: "comp::billing", target: "rc::rc_billing", type: "CAUSED_BY" },
    { source: "conv::conv_00001", target: "comp::billing", type: "MENTIONS" },
  ],
  center: "rc::rc_billing",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("toElements", () => {
  it("should map nodes and edges to cytoscape element definitions", () => {
    const els = toElements(SUB);
    expect(els).toHaveLength(5); // 3 nodes + 2 edges

    const rc = els.find((e) => e.data.id === "rc::rc_billing");
    expect(rc?.data).toMatchObject({ id: "rc::rc_billing", type: "RootCause", label: "billing" });

    const edge = els.find((e) => e.data.source === "comp::billing");
    expect(edge?.data).toMatchObject({ source: "comp::billing", target: "rc::rc_billing", type: "CAUSED_BY" });
  });

  it("should assign a per-type fill color to each node", () => {
    const els = toElements(SUB);
    const colorOf = (id: string) => els.find((e) => e.data.id === id)?.data.color;
    // token vars are unresolved in jsdom → falls back to the type literals
    expect(colorOf("rc::rc_billing")).toBe("#e8a13a"); // RootCause
    expect(colorOf("comp::billing")).toBe("#5b9bd5"); // Component
    expect(colorOf("conv::conv_00001")).toBe("#8e6fd8"); // Conversation
  });
});

describe("graphStylesheet", () => {
  it("should apply the glow only to RootCause nodes (others have no glow)", () => {
    const sheet = graphStylesheet("#e8a13a");

    const rc = sheet.find(
      (s) => typeof s.selector === "string" && s.selector.includes('node[type="RootCause"]'),
    );
    expect(rc).toBeDefined();
    expect(rc!.style).toMatchObject({ "underlay-color": "#e8a13a" });
    expect(Number(rc!.style["underlay-opacity"])).toBeGreaterThan(0);

    // no other selector carries an underlay glow
    const otherGlow = sheet.filter(
      (s) =>
        !(typeof s.selector === "string" && s.selector.includes("RootCause")) &&
        s.style &&
        Number((s.style as Record<string, unknown>)["underlay-opacity"] ?? 0) > 0,
    );
    expect(otherGlow).toHaveLength(0);
  });
});

describe("EvidencePanel", () => {
  it("should fetch the subgraph with expand=rc::<key> when root_cause_key is present", async () => {
    const getSubgraphFn = vi.fn().mockResolvedValue(SUB);
    render(
      <EvidencePanel
        subgraphRef={{ top_component: "billing", root_cause_key: "rc_billing" }}
        getSubgraphFn={getSubgraphFn}
      />,
    );

    await waitFor(() => expect(getSubgraphFn).toHaveBeenCalledTimes(1));
    expect(getSubgraphFn).toHaveBeenCalledWith({ expand: "rc::rc_billing", hops: 1 });
    await waitFor(() =>
      expect(screen.getByTestId("cytoscape")).toHaveAttribute("data-count", "5"),
    );
  });

  it("should fetch the default snapshot (no expand) when root_cause_key is absent", async () => {
    const getSubgraphFn = vi.fn().mockResolvedValue(SUB);
    render(
      <EvidencePanel subgraphRef={{ top_component: "billing" }} getSubgraphFn={getSubgraphFn} />,
    );

    await waitFor(() => expect(getSubgraphFn).toHaveBeenCalledTimes(1));
    expect(getSubgraphFn).toHaveBeenCalledWith();
  });

  it("should render each evidence item with its D/S/G arm tags and score (mono)", () => {
    const getSubgraphFn = vi.fn().mockResolvedValue(SUB);
    render(
      <EvidencePanel
        subgraphRef={{ root_cause_key: "rc_billing" }}
        getSubgraphFn={getSubgraphFn}
        evidence={[
          { id: "conv_00001", arms: ["dense", "graph"], score: 0.82 },
          { id: "conv_00002", arms: ["sparse"], score: 0.41 },
        ]}
      />,
    );

    const first = screen.getByText("conv_00001").closest("[data-testid='evidence-item']")!;
    expect(within(first as HTMLElement).getByText("D")).toBeInTheDocument();
    expect(within(first as HTMLElement).getByText("G")).toBeInTheDocument();
    expect(within(first as HTMLElement).queryByText("S")).not.toBeInTheDocument();
    const score = within(first as HTMLElement).getByText("0.82");
    expect(score).toHaveClass("mono");
  });

  it("should call onExplore when the 탐색 action is clicked", async () => {
    const onExplore = vi.fn();
    render(
      <EvidencePanel
        subgraphRef={{ root_cause_key: "rc_billing" }}
        getSubgraphFn={vi.fn().mockResolvedValue(SUB)}
        onExplore={onExplore}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /탐색/ }));
    expect(onExplore).toHaveBeenCalledTimes(1);
  });

  it("should render a placeholder and not fetch when subgraphRef is null", () => {
    const getSubgraphFn = vi.fn().mockResolvedValue(SUB);
    render(<EvidencePanel subgraphRef={null} getSubgraphFn={getSubgraphFn} />);

    expect(getSubgraphFn).not.toHaveBeenCalled();
    expect(screen.getByTestId("evidence-placeholder")).toBeInTheDocument();
  });

  it("should show an error state (not stay loading) when the subgraph fetch fails", async () => {
    const getSubgraphFn = vi.fn().mockRejectedValue(new Error("network"));
    render(
      <EvidencePanel subgraphRef={{ root_cause_key: "rc_billing" }} getSubgraphFn={getSubgraphFn} />,
    );

    await waitFor(() => expect(screen.getByTestId("evidence-error")).toBeInTheDocument());
    expect(screen.queryByTestId("cytoscape")).not.toBeInTheDocument();
  });
});
