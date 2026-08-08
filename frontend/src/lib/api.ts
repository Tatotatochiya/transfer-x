import axios from "axios";
import type { AxiosRequestConfig } from "axios";
import { useAuthStore } from "../store/auth";

// Explicit VITE_API_BASE_URL wins (Railway prod build). Otherwise: the Vite
// dev server proxies /api/* to the backend (vite.config.ts), but a built
// production bundle (Docker's `serve -s dist`) has no proxy, so it must hit
// the backend directly on whatever host served this page — not a baked-in
// "localhost", which breaks as soon as the page is loaded from another device.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV
    ? "/api"
    : `${window.location.protocol}//${window.location.hostname}:8001`);
const _baseURL = API_BASE_URL;
console.log("[api] baseURL =", _baseURL);

// No default Content-Type: axios sets application/json for object bodies
// automatically, and a hardcoded default would break multipart/form-data uploads
// (axios 1.x serializes FormData to JSON when Content-Type is application/json).
const api = axios.create({
  baseURL: _baseURL,
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
          }>(`${_baseURL}/auth/refresh`, { refresh_token: refreshToken });

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
