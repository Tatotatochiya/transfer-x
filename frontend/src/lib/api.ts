import axios from "axios";
import type { AxiosRequestConfig } from "axios";
import { useAuthStore } from "../store/auth";

const _baseURL = import.meta.env.VITE_API_BASE_URL ?? "/api";
console.log("[api] baseURL =", _baseURL);

const api = axios.create({
  baseURL: _baseURL,
  headers: { "Content-Type": "application/json" },
});

// ── Request interceptor — attach access token ─────────────────────────────────

api.interceptors.request.use((config) => {
  const token: string | null = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response interceptor — silent token refresh on 401 ───────────────────────

const SKIP_REFRESH = ["/auth/login", "/auth/refresh", "/auth/logout"];

let _refreshing: Promise<string> | null = null;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original: AxiosRequestConfig & { _retry?: boolean } = error.config;
    const url: string = original?.url ?? "";

    if (
      error.response?.status !== 401 ||
      original._retry ||
      SKIP_REFRESH.some((path) => url.includes(path))
    ) {
      return Promise.reject(error);
    }

    original._retry = true;

    try {
      // Deduplicate concurrent 401s into a single refresh call
      if (!_refreshing) {
        _refreshing = (async () => {
          const refreshToken: string | null =
            useAuthStore.getState().refreshToken;
          if (!refreshToken) throw new Error("No refresh token");

          const { data } = await axios.post<{
            access_token: string;
            refresh_token: string;
          }>(`${import.meta.env.VITE_API_BASE_URL ?? "/api"}/auth/refresh`, { refresh_token: refreshToken });

          useAuthStore
            .getState()
            .setTokens(data.access_token, data.refresh_token);
          return data.access_token;
        })().finally(() => {
          _refreshing = null;
        });
      }

      const newAccessToken = await _refreshing;
      original.headers = {
        ...original.headers,
        Authorization: `Bearer ${newAccessToken}`,
      };
      return api(original);
    } catch {
      // Refresh failed — clear auth state; router guard will redirect to /login
      useAuthStore.getState().logout();
      return Promise.reject(error);
    }
  }
);

export default api;
