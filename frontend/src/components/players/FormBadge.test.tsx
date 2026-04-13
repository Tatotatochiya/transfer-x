import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FormBadge from "./FormBadge";

describe("FormBadge", () => {
  it("renders score rounded to nearest integer", () => {
    render(<FormBadge score={37.61} />);
    expect(screen.getByText(/38/)).toBeInTheDocument();
  });

  it("does not crash when score is a numeric string (Decimal from API)", () => {
    // Pydantic Decimal fields used to serialize as strings — guard against regression
    render(<FormBadge score={"37.61" as unknown as number} />);
    expect(screen.getByText(/38/)).toBeInTheDocument();
  });

  it("shows up arrow for positive trend > 5", () => {
    render(<FormBadge score={70} trend={8} />);
    expect(screen.getByText(/↑/)).toBeInTheDocument();
  });

  it("shows down arrow for negative trend < -5", () => {
    render(<FormBadge score={40} trend={-9} />);
    expect(screen.getByText(/↓/)).toBeInTheDocument();
  });

  it("shows flat arrow for trend between -5 and 5", () => {
    render(<FormBadge score={55} trend={2} />);
    expect(screen.getByText(/→/)).toBeInTheDocument();
  });

  it("shows no arrow when trend is null", () => {
    const { container } = render(<FormBadge score={60} trend={null} />);
    expect(container.textContent).not.toMatch(/[↑↓→]/);
  });

  it("applies emerald colour for score >= 75", () => {
    const { container } = render(<FormBadge score={80} />);
    expect(container.firstChild).toHaveClass("bg-emerald-500/20");
  });

  it("applies amber colour for score 35–54", () => {
    const { container } = render(<FormBadge score={45} />);
    expect(container.firstChild).toHaveClass("bg-amber-500/20");
  });

  it("applies red colour for score < 35", () => {
    const { container } = render(<FormBadge score={20} />);
    expect(container.firstChild).toHaveClass("bg-red-500/20");
  });

  it("renders md size with larger padding", () => {
    const { container } = render(<FormBadge score={60} size="md" />);
    expect(container.firstChild).toHaveClass("px-2.5");
  });
});
