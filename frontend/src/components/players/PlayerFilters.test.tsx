import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PlayerFilters, { DEFAULT_PLAYER_FILTERS } from "./PlayerFilters";
import type { PlayerFilterState } from "./PlayerFilters";

function setup(overrides: Partial<PlayerFilterState> = {}) {
  const filters: PlayerFilterState = { ...DEFAULT_PLAYER_FILTERS, ...overrides };
  const onChange = vi.fn();
  render(<PlayerFilters filters={filters} onChange={onChange} />);
  return { onChange };
}

describe("PlayerFilters", () => {
  it("renders search, position, status, sort controls", () => {
    setup();
    expect(screen.getByPlaceholderText(/Search players/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("All positions")).toBeInTheDocument();
    expect(screen.getByDisplayValue("All statuses")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Name A→Z")).toBeInTheDocument();
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

  it("calls onChange with correct position when position selected", async () => {
    const { onChange } = setup();
    await userEvent.selectOptions(screen.getByDisplayValue("All positions"), "FWD");
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ position: "FWD" })
    );
  });

  it("calls onChange with sort_by=age sort_dir=asc for Youngest first", async () => {
    const { onChange } = setup();
    await userEvent.selectOptions(screen.getByDisplayValue("Name A→Z"), "Youngest first");
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ sort_by: "age", sort_dir: "asc" })
    );
  });

  it("calls onChange with sort_by=age sort_dir=desc for Oldest first", async () => {
    const { onChange } = setup();
    await userEvent.selectOptions(screen.getByDisplayValue("Name A→Z"), "Oldest first");
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ sort_by: "age", sort_dir: "desc" })
    );
  });

  it("toggles open_to_offers on click", async () => {
    const { onChange } = setup({ open_to_offers: false });
    const toggle = screen.getByText("Open to offers").previousSibling as HTMLElement;
    await userEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ open_to_offers: true })
    );
  });

  it("shows Clear all button only when filters are active", () => {
    const { rerender } = render(
      <PlayerFilters filters={DEFAULT_PLAYER_FILTERS} onChange={vi.fn()} />
    );
    expect(screen.queryByText("Clear all")).not.toBeInTheDocument();

    rerender(
      <PlayerFilters
        filters={{ ...DEFAULT_PLAYER_FILTERS, search: "Salah" }}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText("Clear all")).toBeInTheDocument();
  });

  it("resets to defaults when Clear all clicked", async () => {
    const onChange = vi.fn();
    render(
      <PlayerFilters
        filters={{ ...DEFAULT_PLAYER_FILTERS, search: "Salah", position: "FWD" }}
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByText("Clear all"));
    expect(onChange).toHaveBeenCalledWith(DEFAULT_PLAYER_FILTERS);
  });

  it("calls onChange with min_age when age input changes", () => {
    const { onChange } = setup();
    fireEvent.change(screen.getByPlaceholderText("Min age"), { target: { value: "25" } });
    const lastCall = onChange.mock.calls.at(-1)[0] as PlayerFilterState;
    expect(lastCall.min_age).toBe("25");
  });

  it("calls onChange with nationality when nationality input changes", () => {
    const { onChange } = setup();
    fireEvent.change(screen.getByPlaceholderText("Nationality…"), { target: { value: "Brazil" } });
    const lastCall = onChange.mock.calls.at(-1)[0] as PlayerFilterState;
    expect(lastCall.nationality).toBe("Brazil");
  });
});
