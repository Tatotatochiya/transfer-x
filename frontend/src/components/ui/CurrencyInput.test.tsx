import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CurrencyInput from "./CurrencyInput";

describe("CurrencyInput", () => {
  it("displays the raw value with thousands separators", () => {
    render(<CurrencyInput value="1200000" onChange={() => {}} />);
    expect(screen.getByRole("textbox")).toHaveValue("1,200,000");
  });

  it("displays decimals with separators on the integer part only", () => {
    render(<CurrencyInput value="1234.5" onChange={() => {}} />);
    expect(screen.getByRole("textbox")).toHaveValue("1,234.5");
  });

  it("renders empty when value is empty", () => {
    render(<CurrencyInput value="" onChange={() => {}} />);
    expect(screen.getByRole("textbox")).toHaveValue("");
  });

  it("calls onChange with the raw digits, not the formatted display", () => {
    const onChange = vi.fn();
    render(<CurrencyInput value="" onChange={onChange} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "1200000" } });
    expect(onChange).toHaveBeenCalledWith("1200000");
  });

  it("strips commas already present in the typed value before reporting it", () => {
    const onChange = vi.fn();
    render(<CurrencyInput value="1,200,000" onChange={onChange} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "1,200,0001" } });
    expect(onChange).toHaveBeenCalledWith("12000001");
  });

  it("ignores non-numeric input and does not call onChange", () => {
    const onChange = vi.fn();
    render(<CurrencyInput value="100" onChange={onChange} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "100abc" } });
    expect(onChange).not.toHaveBeenCalled();
  });

  it("rejects a third decimal place", () => {
    const onChange = vi.fn();
    render(<CurrencyInput value="1.23" onChange={onChange} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "1.234" } });
    expect(onChange).not.toHaveBeenCalled();
  });

  it("spreads extra input props (id, placeholder, required) onto the input", () => {
    render(<CurrencyInput value="" onChange={() => {}} id="fee" placeholder="Amount" required />);
    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("id", "fee");
    expect(input).toHaveAttribute("placeholder", "Amount");
    expect(input).toBeRequired();
  });
});
