import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CiteText, citeQuestion } from "./CiteLink";

describe("citeQuestion", () => {
  it("should build '<id> 근거 대화 보여줘' for a given id", () => {
    expect(citeQuestion("rc_support")).toBe("rc_support 근거 대화 보여줘");
  });
});

describe("CiteText", () => {
  it("should render an rc_ id token as a clickable link", () => {
    render(<CiteText text="루트원인 rc_support 를 보세요" onCite={vi.fn()} />);
    const link = screen.getByRole("button", { name: "rc_support" });
    expect(link).toBeInTheDocument();
  });

  it("should call onCite with the exact id when a cite link is clicked", () => {
    const onCite = vi.fn();
    render(<CiteText text="근거: conv_00012 참고" onCite={onCite} />);

    fireEvent.click(screen.getByRole("button", { name: "conv_00012" }));

    expect(onCite).toHaveBeenCalledTimes(1);
    expect(onCite).toHaveBeenCalledWith("conv_00012");
  });

  it("should render the cite link id in a mono element", () => {
    render(<CiteText text="rc_ORDER 확인" onCite={vi.fn()} />);
    const link = screen.getByRole("button", { name: "rc_ORDER" });
    expect(link).toHaveClass("mono");
  });

  it("should linkify multiple distinct ids as separate links", () => {
    render(<CiteText text="rc_ORDER 와 sym_timeout 와 conv_00001" onCite={vi.fn()} />);
    expect(screen.getByRole("button", { name: "rc_ORDER" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "sym_timeout" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "conv_00001" })).toBeInTheDocument();
  });

  it("should linkify an uppercase/numeric id (rc_ORDER, conv_00012)", () => {
    render(<CiteText text="rc_ORDER conv_00012" onCite={vi.fn()} />);
    expect(screen.getByRole("button", { name: "rc_ORDER" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "conv_00012" })).toBeInTheDocument();
  });

  it("should render plain text unchanged when no id token is present", () => {
    render(<CiteText text="위험 ₩6,484,500, 회수가능 ₩3,306,600" onCite={vi.fn()} />);
    expect(screen.getByText("위험 ₩6,484,500, 회수가능 ₩3,306,600")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("should not linkify a word with underscore but no known prefix (foo_bar, order_id)", () => {
    render(<CiteText text="foo_bar 와 order_id 는 링크 아님" onCite={vi.fn()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("should disable cite links and not fire onCite when disabled is true", () => {
    const onCite = vi.fn();
    render(<CiteText text="rc_auth 확인" onCite={onCite} disabled />);

    const link = screen.getByRole("button", { name: "rc_auth" });
    expect(link).toBeDisabled();
    fireEvent.click(link);
    expect(onCite).not.toHaveBeenCalled();
  });

  it("should linkify the rc key and conv ids the backend now embeds in answer prose (#46)", () => {
    // Mirrors src/server/routers/chat.py answer branch — the composed answer now
    // carries the rootcause key + sample conversation ids so the operator can
    // traverse the graph as a conversation (the live gap this documented is closed).
    const liveAnswer =
      "루트원인 rc_auth — 'auth' 관련 근거 12건. 위험 ₩6,484,500, 회수가능 ₩3,306,600, " +
      "confidence 0.82. 가설: 게이트웨이 타임아웃. 근거 대화: conv_00001, conv_00002.";
    render(<CiteText text={liveAnswer} onCite={vi.fn()} />);
    expect(screen.getByRole("button", { name: "rc_auth" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "conv_00001" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "conv_00002" })).toBeInTheDocument();
  });
});
