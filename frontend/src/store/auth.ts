import { create } from "zustand";
import type { User } from "../types/api";

export const REFRESH_TOKEN_KEY = "transferx-refresh";

/**
 * "View as this club" (admin panel) opens a tab at /view-as#view_as=<token>:
 * a read-only, 30-minute session as the club's owner. The token is taken from
 * the URL fragment (never sent to the server or kept in history) and held in
 * memory only. This tab never reads or writes the stored refresh token, which
 * belongs to the staff member's own session in their other tabs.
 */
function takeViewAsToken(): string | null {
  if (typeof window === "undefined") return null;
  const m = /^#view_as=([\w.-]+)$/.exec(window.location.hash);
  if (!m) return null;
  window.history.replaceState(null, "", window.location.pathname);
  return m[1];
}

const VIEW_AS_TOKEN = takeViewAsToken();

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isBootstrapping: boolean;
  /** This tab is a read-only "view as" session. */
  viewAs: boolean;

  // Actions
  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  setBootstrapping: (v: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: VIEW_AS_TOKEN,
  // Hydrate refresh token from localStorage on store creation (not in a
  // view-as tab: that session has no refresh token of its own).
  refreshToken: VIEW_AS_TOKEN ? null : localStorage.getItem(REFRESH_TOKEN_KEY),
  isBootstrapping: VIEW_AS_TOKEN ? true : !!localStorage.getItem(REFRESH_TOKEN_KEY),
  viewAs: VIEW_AS_TOKEN !== null,

  setTokens: (accessToken, refreshToken) => {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    set({ accessToken, refreshToken });
  },

  setUser: (user) => set({ user }),

  setBootstrapping: (v) => set({ isBootstrapping: v }),

  logout: () => {
    // Leaving a view-as tab must not sign the staff member out of their own tabs.
    if (!useAuthStore.getState().viewAs) localStorage.removeItem(REFRESH_TOKEN_KEY);
    set({ user: null, accessToken: null, refreshToken: null, isBootstrapping: false, viewAs: false });
  },
}));
