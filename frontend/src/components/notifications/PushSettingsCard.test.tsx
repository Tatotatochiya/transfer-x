import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/utils";
import PushSettingsCard from "./PushSettingsCard";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }));
vi.mock("../../lib/api", () => ({ default: api, API_BASE_URL: "/api" }));
const pushState = vi.hoisted(() => ({ value: "default" as string }));
const subscribe = vi.hoisted(() => vi.fn());
vi.mock("../../lib/push", () => ({
  usePushState: () => ({ data: pushState.value, isLoading: false }),
  useThisDeviceEndpoint: () => ({ data: pushState.value === "granted-subscribed" ? "https://push/this" : null }),
  useRefreshPush: () => () => {},
  subscribe,
  unsubscribe: vi.fn(),
}));
vi.mock("../../context/ToastContext", () => ({ useToast: () => ({ addToast: vi.fn() }) }));

const PREFS = {
  lite_mode: false, lite_mode_is_default: true, text_scale: "NORMAL",
  push_your_move: "SOUND", push_heads_up: "SILENT", push_summary: true, summary_local_time: "08:00:00",
  quiet_hours_enabled: true, quiet_start: "22:00:00", quiet_end: "07:00:00", timezone: "Europe/London",
  push_hide_amounts: false,
};

describe("PushSettingsCard", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.patch.mockReset();
    api.get.mockImplementation((url: string) =>
      Promise.resolve({ data: url === "/users/me/preferences" ? PREFS : [
        { id: "d1", platform: "DESKTOP", label: "Mac · Chrome", endpoint: "https://push/other", created_at: "2026-10-01T10:00:00Z", last_success_at: null },
      ] }),
    );
  });

  it("asks to turn on, then shows the tier, quiet hours and hide-amounts settings", async () => {
    pushState.value = "default";
    renderWithProviders(<PushSettingsCard />);
    await userEvent.click(screen.getByRole("button", { name: "Turn on notifications" }));
    expect(subscribe).toHaveBeenCalled();
    expect(await screen.findByRole("radiogroup", { name: "Your move" })).toBeInTheDocument();
    expect(screen.getByText("Hide amounts on the lock screen")).toBeInTheDocument();
    expect(screen.getByText("Mac · Chrome")).toBeInTheDocument();
  });

  it("saves a tier change and the hide-amounts switch", async () => {
    pushState.value = "granted-subscribed";
    api.patch.mockResolvedValue({ data: PREFS });
    renderWithProviders(<PushSettingsCard />);
    await userEvent.click(within(await screen.findByRole("radiogroup", { name: "Heads-up" })).getByRole("radio", { name: "Off" }));
    expect(api.patch).toHaveBeenCalledWith("/users/me/preferences", { push_heads_up: "OFF" });
    await userEvent.click(screen.getByRole("switch", { name: "Hide amounts on the lock screen" }));
    expect(api.patch).toHaveBeenCalledWith("/users/me/preferences", { push_hide_amounts: true });
  });

  it("explains the Home Screen step on an iPhone tab, and email as the fallback", async () => {
    pushState.value = "needs-install";
    const { unmount } = renderWithProviders(<PushSettingsCard />);
    expect(screen.getByText("Add TransferX to your Home Screen first")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Turn on notifications" })).not.toBeInTheDocument();
    unmount();

    pushState.value = "unsupported";
    renderWithProviders(<PushSettingsCard />);
    expect(screen.getByText("This browser can't show notifications. You'll still get email.")).toBeInTheDocument();
  });
});
