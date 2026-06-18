import { useCallback, useEffect, useRef } from "react"; // useRef kept — guards against double-invocation in React Strict Mode
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import api from "../lib/api";
import type { TokenResponse, User } from "../types/api";

export function useAuth() {
  const { user, accessToken, refreshToken, setTokens, setUser, setBootstrapping, logout } =
    useAuthStore();
  const queryClient = useQueryClient();

  const bootstrapped = useRef(false);

  // On mount: if we have a refresh token but no access token, silently refresh
  // so the user stays logged in across page reloads.
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    if (!refreshToken || accessToken) {
      setBootstrapping(false);
      return;
    }

    api
      .post<TokenResponse>("/auth/refresh", { refresh_token: refreshToken })
      .then(({ data }) => {
        setTokens(data.access_token, data.refresh_token);
        return api.get<User>("/auth/me");
      })
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
