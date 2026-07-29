import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RelatedChips, SEED_CHIPS } from "./RelatedChips";

describe("RelatedChips", () => {
  it("should render each question as a clickable chip", () => {
    const questions = ["ORDER 근거 대화 보여줘", "ORDER 위험액은 얼마야?"];
    render(<RelatedChips questions={questions} onPick={vi.fn()} />);

    questions.forEach((q) =>
      expect(screen.getByRole("button", { name: q })).toBeInTheDocument(),
    );
  });

  it("should call onPick with the question text when a chip is clicked", () => {
    const onPick = vi.fn();
    render(<RelatedChips questions={["ORDER 위험액은 얼마야?"]} onPick={onPick} />);

    fireEvent.click(screen.getByRole("button", { name: "ORDER 위험액은 얼마야?" }));

    expect(onPick).toHaveBeenCalledTimes(1);
    expect(onPick).toHaveBeenCalledWith("ORDER 위험액은 얼마야?");
  });

  it("should render SEED_CHIPS when questions is empty (never empty)", () => {
    render(<RelatedChips questions={[]} onPick={vi.fn()} />);

    expect(SEED_CHIPS.length).toBeGreaterThan(0);
    SEED_CHIPS.forEach((q) =>
      expect(screen.getByRole("button", { name: q })).toBeInTheDocument(),
    );
  });

  it("should disable chips and not fire onPick when disabled is true", () => {
    const onPick = vi.fn();
    render(<RelatedChips questions={["ORDER 위험액은 얼마야?"]} onPick={onPick} disabled />);

    const chip = screen.getByRole("button", { name: "ORDER 위험액은 얼마야?" });
    expect(chip).toBeDisabled();
    fireEvent.click(chip);
    expect(onPick).not.toHaveBeenCalled();
  });
});
