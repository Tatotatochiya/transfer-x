import { create } from "zustand";
import type { User } from "../types/api";

const REFRESH_TOKEN_KEY = "transferx-refresh";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isBootstrapping: boolean;

  // Actions
  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  setBootstrapping: (v: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  // Hydrate refresh token from localStorage on store creation
  refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
  isBootstrapping: !!localStorage.getItem(REFRESH_TOKEN_KEY),

  setTokens: (accessToken, refreshToken) => {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    set({ accessToken, refreshToken });
  },

  setUser: (user) => set({ user }),

  setBootstrapping: (v) => set({ isBootstrapping: v }),

  logout: () => {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    set({ user: null, accessToken: null, refreshToken: null, isBootstrapping: false });
  },
}));
