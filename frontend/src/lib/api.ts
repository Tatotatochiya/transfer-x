import axios from "axios";
import type { AxiosRequestConfig } from "axios";
import { REFRESH_TOKEN_KEY, useAuthStore } from "../store/auth";

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

/**
 * Swap the refresh token for a new access token, once at a time. Refresh
 * tokens rotate, so two refreshes with the same token race: the second is
 * refused and the user is signed out. Everything that refreshes (session
 * restore on page load, and a 401 below) shares this one call.
 */
export function refreshAccessToken(): Promise<string> {
  if (!_refreshing) {
    _refreshing = (async () => {
      // The stored token is shared by every tab, so it is the freshest one:
      // another tab may have rotated it since this tab loaded. (A read-only
      // "view as" tab has no refresh token of its own and never reads it.)
      const viewAs = useAuthStore.getState().viewAs;
      const stored = () => (viewAs ? null : safeStored());
      const used = stored() ?? useAuthStore.getState().refreshToken;
      if (!used) throw new Error("No refresh token");

      const swap = (token: string) => axios.post<{ access_token: string; refresh_token: string }>(
        `${_baseURL}/auth/refresh`, { refresh_token: token },
      );
      let data;
      try {
        ({ data } = await swap(used));
      } catch (err) {
        // Two tabs refreshed at the same moment with the same token: the
        // other one won and stored the new token. Use that, once, instead of
        // signing this tab out.
        // Its response may still be on the way, so give it a moment to land.
        let now = stored();
        for (let i = 0; i < 3 && (!now || now === used); i++) {
          await new Promise((r) => setTimeout(r, 500));
          now = stored();
        }
        if (!now || now === used) throw err;
        ({ data } = await swap(now));
      }

      useAuthStore.getState().setTokens(data.access_token, data.refresh_token);
      return data.access_token;
    })().finally(() => {
      _refreshing = null;
    });
  }
  return _refreshing;
}

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
      const newAccessToken = await refreshAccessToken();
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


function safeStored(): string | null {
  try {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}
