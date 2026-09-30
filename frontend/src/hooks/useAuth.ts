import { useCallback, useEffect, useRef } from "react"; // useRef kept — guards against double-invocation in React Strict Mode
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import api, { refreshAccessToken } from "../lib/api";
import type { TokenResponse, User } from "../types/api";

/**
 * Restore the session on page load: with a refresh token but no access token,
 * refresh silently. Called once, from the app's global setup. It used to run
 * inside `useAuth`, so every component using `useAuth` ran it too, and a public
 * page's first requests (sent before the session is back) refreshed on their
 * 401 at the same time: refreshes raced with the same rotated token, the loser
 * logged the user out, and a reload of the player market showed it signed
 * out. Now it runs once and shares the client's single refresh.
 */
export function useAuthBootstrap() {
  const { accessToken, refreshToken, setUser, setBootstrapping, logout } = useAuthStore();
  const bootstrapped = useRef(false);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    if (!refreshToken || accessToken) {
      setBootstrapping(false);
      return;
    }

    refreshAccessToken()
      .then(() => api.get<User>("/auth/me"))
      .then((res) => {
        if (res) setUser(res.data);
      })
      .catch(() => {
        logout();
      })
      .finally(() => {
        setBootstrapping(false);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}

export function useAuth() {
  const { user, accessToken, refreshToken, setTokens, setUser, logout } =
    useAuthStore();
  const queryClient = useQueryClient();

  const login = useCallback(
    async (email: string, password: string): Promise<User> => {
      const { data } = await api.post<TokenResponse>("/auth/login", {
        email,
        password,
      });
      setTokens(data.access_token, data.refresh_token);
      const { data: me } = await api.get<User>("/auth/me");
      setUser(me);
      return me;
    },
    [setTokens, setUser]
  );

  const logoutAndRevoke = useCallback(async () => {
    try {
      if (refreshToken) {
        await api.post("/auth/logout", { refresh_token: refreshToken });
      }
    } finally {
      logout();
      queryClient.clear();
    }
  }, [refreshToken, logout, queryClient]);

  return {
    user,
    accessToken,
    isAuthenticated: !!accessToken,
    isSuperuser: user?.is_superuser ?? false,
    userType: user?.user_type ?? null,
    isClub: user?.user_type === "CLUB",
    isAgent: user?.user_type === "AGENT",
    isPlayer: user?.user_type === "PLAYER",
    login,
    logout: logoutAndRevoke,
  };
}
