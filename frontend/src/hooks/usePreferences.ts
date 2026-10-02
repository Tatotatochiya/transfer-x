import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../lib/api";

/** Lite mode's text size (docs/feature_spec/lite-mode): applies inside Lite only. */
export type TextScale = "NORMAL" | "LARGE" | "LARGER";

/** How a notification tier arrives on a phone (mobile notifications §4.1). */
export type PushMode = "SOUND" | "SILENT" | "OFF";

export interface PushSettings {
  push_your_move: PushMode;
  push_heads_up: PushMode;
  push_summary: boolean;
  /** "HH:MM:SS" in the person's timezone. */
  summary_local_time: string;
  quiet_hours_enabled: boolean;
  quiet_start: string;
  quiet_end: string;
  timezone: string;
  push_hide_amounts: boolean;
}

export interface Preferences extends PushSettings {
  lite_mode: boolean;
  /** True while the user has never chosen, so lite_mode is their role's default. */
  lite_mode_is_default: boolean;
  text_scale: TextScale;
}

export const TEXT_SCALE_PERCENT: Record<TextScale, number> = { NORMAL: 100, LARGE: 112.5, LARGER: 125 };

// Remembered on this device so Lite opens at the right size before the
// preferences arrive (no jump on first paint); the server copy is the truth.
const SCALE_KEY = "transferx-lite-text-scale";

export function cachedTextScale(): TextScale {
  try {
    const v = localStorage.getItem(SCALE_KEY);
    return v === "LARGE" || v === "LARGER" ? v : "NORMAL";
  } catch {
    return "NORMAL";
  }
}

function cacheTextScale(scale: TextScale) {
  try {
    localStorage.setItem(SCALE_KEY, scale);
  } catch {
    /* private mode: the server copy still applies once loaded */
  }
}

export function usePreferences(enabled = true) {
  return useQuery<Preferences>({
    queryKey: ["users", "me", "preferences"],
    queryFn: () =>
      api.get<Preferences>("/users/me/preferences").then((r) => {
        cacheTextScale(r.data.text_scale);
        return r.data;
      }),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Omit<Preferences, "lite_mode_is_default">>) =>
      api.patch<Preferences>("/users/me/preferences", body).then((r) => r.data),
    onSuccess: (prefs) => {
      cacheTextScale(prefs.text_scale);
      queryClient.setQueryData(["users", "me", "preferences"], prefs);
    },
  });
}
