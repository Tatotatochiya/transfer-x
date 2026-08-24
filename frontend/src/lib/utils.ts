// ── Currency ──────────────────────────────────────────────────────────────────

import { usePreferencesStore } from "../store/preferences";

const CURRENCY_SYMBOLS: Record<string, string> = { GBP: "£", EUR: "€", USD: "$" };

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  const symbol = CURRENCY_SYMBOLS[usePreferencesStore.getState().currency];
  return symbol + Math.round(value).toLocaleString("en-GB");
}

/** Short form for narrow cells — `£52.0m`, `£450k`. Full precision (see
 *  `formatCurrency`) is unbreakable text and overflows a flex cell. */
export function formatCompactCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  const symbol = CURRENCY_SYMBOLS[usePreferencesStore.getState().currency];
  const n = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (n >= 1_000_000) return `${sign}${symbol}${(n / 1_000_000).toFixed(1)}m`;
  if (n >= 1_000) return `${sign}${symbol}${Math.round(n / 1_000)}k`;
  return `${sign}${symbol}${Math.round(n)}`;
}

export function formatWage(value: number | null | undefined): string {
  if (value == null) return "—";
  const symbol = CURRENCY_SYMBOLS[usePreferencesStore.getState().currency];
  return symbol + Math.round(value).toLocaleString("en-GB") + "/wk";
}

// ── Dates ─────────────────────────────────────────────────────────────────────

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDatePref(iso: string | null | undefined): string {
  if (!iso) return "—";
  if (usePreferencesStore.getState().dateFormat === "relative") {
    const ms = Date.now() - new Date(iso).getTime();
    if (ms < 60_000) return "just now";
    if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
    if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
    if (ms < 7 * 86_400_000) return `${Math.floor(ms / 86_400_000)}d ago`;
  }
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

// ── Deadline countdown ────────────────────────────────────────────────────────

export type DeadlineState = "ok" | "warning" | "danger" | "expired";

export interface DeadlineResult {
  label: string;
  state: DeadlineState;
}

export function formatDeadline(iso: string | null | undefined): DeadlineResult {
  if (!iso) return { label: "No deadline", state: "ok" };

  const ms = new Date(iso).getTime() - Date.now();

  if (ms <= 0) return { label: "Expired", state: "expired" };

  const totalSeconds = Math.floor(ms / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  let label: string;
  if (days > 0) {
    label = `${days}d ${hours}h`;
  } else if (hours > 0) {
    label = `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    label = `${minutes}m ${seconds}s`;
  } else {
    label = `${seconds}s`;
  }

  const state: DeadlineState =
    ms < 15 * 60 * 1000 ? "danger" : ms < 60 * 60 * 1000 ? "warning" : "ok";

  return { label, state };
}

// ── Class names ───────────────────────────────────────────────────────────────

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

// ── API error extraction ───────────────────────────────────────────────────────

import type { AxiosError } from "axios";

/** Extract a human-readable message from an Axios error response. */
export function getApiError(err: unknown, fallback = "Something went wrong."): string {
  const axiosErr = err as AxiosError<{ detail?: unknown }>;
  const detail = axiosErr?.response?.data?.detail;
  if (!detail) return fallback;
  // FastAPI validation errors: array of {msg, loc, ...}
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (typeof e === "object" && e !== null && "msg" in e ? String((e as Record<string, unknown>).msg) : String(e)))
      .join("; ");
  }
  if (typeof detail === "string") return detail;
  return fallback;
}
