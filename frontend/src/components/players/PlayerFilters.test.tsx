import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PlayerFilters, { DEFAULT_PLAYER_FILTERS } from "./PlayerFilters";
import type { PlayerFilterState } from "./PlayerFilters";

function setup(overrides: Partial<PlayerFilterState> = {}) {
  const filters: PlayerFilterState = { ...DEFAULT_PLAYER_FILTERS, ...overrides };
  const onChange = vi.fn();
  const onViewChange = vi.fn();
  render(<PlayerFilters filters={filters} onChange={onChange} view="grid" onViewChange={onViewChange} />);
  return { onChange, onViewChange };
}

describe("PlayerFilters", () => {
  it("renders search, position pills, and the primary rail fields", () => {
    setup();
    expect(screen.getByPlaceholderText(/Search players/i)).toBeInTheDocument();
    expect(screen.getByText("GK")).toBeInTheDocument();
    expect(screen.getByText("DEF")).toBeInTheDocument();
    expect(screen.getByText("MID")).toBeInTheDocument();
    expect(screen.getByText("FWD")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Min age")).toBeInTheDocument();
  });

  it("calls onChange when search text changes", () => {
    const { onChange } = setup();
    // fireEvent.change fires a single event with the full value — needed for controlled inputs
    // because userEvent.type fires per-character but parent state doesn't update between calls.
    fireEvent.change(screen.getByPlaceholderText(/Search players/i), { target: { value: "Salah" } });
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls.at(-1)[0] as PlayerFilterState;
    expect(lastCall.search).toBe("Salah");
  });

  it("calls onChange with correct position when a position pill is clicked", async () => {
    const { onChange } = setup();
    await userEvent.click(screen.getByText("FWD"));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ position: "FWD" })
    );
  });

  it("clears the position when its active pill is clicked again", async () => {
    const { onChange } = setup({ position: "FWD" });
    await userEvent.click(screen.getByText("FWD"));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ position: "" })
    );
  });

  it("calls onChange with min_age when age input changes", () => {
    const { onChange } = setup();
    fireEvent.change(screen.getByPlaceholderText("Min age"), { target: { value: "25" } });
    const lastCall = onChange.mock.calls.at(-1)[0] as PlayerFilterState;
    expect(lastCall.min_age).toBe("25");
  });

  it("reveals the secondary fields (status, open to offers, nationality) behind More filters", async () => {
    setup();
    expect(screen.queryByPlaceholderText("Nationality…")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText(/More filters/));
    expect(screen.getByPlaceholderText("Nationality…")).toBeInTheDocument();
  });

  it("toggles open_to_offers on click once More filters is open", async () => {
    const { onChange } = setup({ open_to_offers: false });
    await userEvent.click(screen.getByText(/More filters/));
    const toggle = screen.getByText("Open to offers only").nextSibling as HTMLElement;
    await userEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ open_to_offers: true })
    );
  });

  it("calls onChange with nationality when nationality input changes", async () => {
    const { onChange } = setup();
    await userEvent.click(screen.getByText(/More filters/));
    fireEvent.change(screen.getByPlaceholderText("Nationality…"), { target: { value: "Brazil" } });
    const lastCall = onChange.mock.calls.at(-1)[0] as PlayerFilterState;
    expect(lastCall.nationality).toBe("Brazil");
  });

  it("shows Clear all filters button only when filters are active", () => {
    const { rerender } = render(
      <PlayerFilters filters={DEFAULT_PLAYER_FILTERS} onChange={vi.fn()} view="grid" onViewChange={vi.fn()} />
    );
    expect(screen.queryByText("Clear all filters")).not.toBeInTheDocument();

    rerender(
      <PlayerFilters
        filters={{ ...DEFAULT_PLAYER_FILTERS, min_age: "20" }}
        onChange={vi.fn()}
        view="grid"
        onViewChange={vi.fn()}
      />
    );
    expect(screen.getByText("Clear all filters")).toBeInTheDocument();
  });

  it("resets to defaults when Clear all filters is clicked", async () => {
    const onChange = vi.fn();
    render(
      <PlayerFilters
        filters={{ ...DEFAULT_PLAYER_FILTERS, min_age: "20", position: "FWD" }}
        onChange={onChange}
        view="grid"
        onViewChange={vi.fn()}
      />
    );
    await userEvent.click(screen.getByText("Clear all filters"));
    expect(onChange).toHaveBeenCalledWith(DEFAULT_PLAYER_FILTERS);
  });
});
