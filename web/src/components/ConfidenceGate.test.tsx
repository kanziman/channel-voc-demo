import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ConfidenceGate } from "./ConfidenceGate";

const CHIPS = ["billing 근거 대화 보여줘", "가장 심각한 컴포넌트는?"];

describe("ConfidenceGate", () => {
  it("should render nothing when gate is 'answer'", () => {
    const { container } = render(
      <ConfidenceGate gate="answer" confidence={0.82} relatedQuestions={CHIPS} onPick={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("should render a refusal banner and answerable-question chips when gate is 'refuse'", () => {
    render(
      <ConfidenceGate gate="refuse" confidence={0} relatedQuestions={CHIPS} onPick={vi.fn()} />,
    );

    expect(screen.getByTestId("confidence-gate")).toHaveAttribute("data-gate", "refuse");
    expect(screen.getByText(/거절|근거 없음/)).toBeInTheDocument();
    CHIPS.forEach((q) =>
      expect(screen.getByRole("button", { name: q })).toBeInTheDocument(),
    );
  });

  it("should render a ⚠ low-confidence banner with confidence (mono) and chips when gate is 'low_confidence'", () => {
    render(
      <ConfidenceGate
        gate="low_confidence"
        confidence={0.32}
        relatedQuestions={CHIPS}
        onPick={vi.fn()}
      />,
    );

    expect(screen.getByTestId("confidence-gate")).toHaveAttribute("data-gate", "low_confidence");
    expect(screen.getByText(/확신.*낮/)).toBeInTheDocument();
    expect(screen.getByText("0.32")).toHaveClass("mono");
    CHIPS.forEach((q) =>
      expect(screen.getByRole("button", { name: q })).toBeInTheDocument(),
    );
  });

  it("should call onPick with the question when a gate chip is clicked", () => {
    const onPick = vi.fn();
    render(
      <ConfidenceGate gate="refuse" confidence={0} relatedQuestions={CHIPS} onPick={onPick} />,
    );

    fireEvent.click(screen.getByRole("button", { name: CHIPS[0] }));
    expect(onPick).toHaveBeenCalledWith(CHIPS[0]);
  });

  it("should still show seed chips (never empty) when relatedQuestions is empty", () => {
    render(<ConfidenceGate gate="refuse" confidence={0} relatedQuestions={[]} onPick={vi.fn()} />);

    expect(screen.getByRole("button", { name: "손실 Top3 루트원인은?" })).toBeInTheDocument();
  });

  it("should also seed-fall-back chips for the low_confidence branch when empty", () => {
    render(
      <ConfidenceGate gate="low_confidence" confidence={0.3} relatedQuestions={[]} onPick={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: "손실 Top3 루트원인은?" })).toBeInTheDocument();
  });
});
