import "@testing-library/jest-dom";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Auto-cleanup after each test
afterEach(() => {
  cleanup();
});

// Silence console.error in tests (React error boundary logs, etc.)
// but re-throw so tests still fail on unexpected errors
const originalError = console.error.bind(console);
console.error = (...args: unknown[]) => {
  // Suppress known React 18/19 act() warnings and prop warnings in tests
  const msg = String(args[0] ?? "");
  if (
    msg.includes("Warning:") ||
    msg.includes("act(") ||
    msg.includes("Not implemented")
  ) {
    return;
  }
  originalError(...args);
};

// Mock IntersectionObserver (not in jsdom)
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock window.matchMedia (not in jsdom)
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
