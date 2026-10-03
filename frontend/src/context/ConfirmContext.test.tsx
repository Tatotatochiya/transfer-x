import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { ConfirmProvider, useAskReason } from "./ConfirmContext";

function Harness() {
  const askReason = useAskReason();
  const [result, setResult] = useState<string>("(none)");
  return (
    <>
      <button onClick={async () => setResult(String(await askReason({ title: "Cancel this sale", message: "Sure?", confirmLabel: "Cancel sale" })))}>
        open
      </button>
      <p data-testid="result">{result}</p>
    </>
  );
}

describe("askReason", () => {
  it("needs at least 5 characters, then resolves with the trimmed reason", async () => {
    render(<ConfirmProvider><Harness /></ConfirmProvider>);
    await userEvent.click(screen.getByText("open"));
    const confirm = screen.getByRole("button", { name: "Cancel sale" });
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByRole("textbox"), "  Too  ");
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByRole("textbox"), " soon");
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);
    expect(screen.getByTestId("result")).toHaveTextContent("Too soon");
  });

  it("resolves null when cancelled", async () => {
    render(<ConfirmProvider><Harness /></ConfirmProvider>);
    await userEvent.click(screen.getByText("open"));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByTestId("result")).toHaveTextContent("null");
  });
});
