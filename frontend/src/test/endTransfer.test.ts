import { describe, expect, it } from "vitest";

/**
 * Any answer that ends a transfer is confirmed through EndTransferDialog
 * (docs/design-system/README.md, "Ending a transfer"): a file that sends a
 * DECLINED answer must use the dialog.
 */
const sources = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], {
  query: "?raw", import: "default", eager: true,
}) as Record<string, string>;

const SENDS_DECLINE = /mutate\(\s*(\{[^}]*agreement:\s*"DECLINED"|"DECLINED")/;

describe("ending a transfer", () => {
  it("every DECLINED answer goes through EndTransferDialog", () => {
    const senders = Object.entries(sources).filter(([, src]) => SENDS_DECLINE.test(src));
    expect(senders.length).toBeGreaterThan(0);
    const unguarded = senders.filter(([, src]) => !src.includes("<EndTransferDialog")).map(([path]) => path);
    expect(unguarded).toEqual([]);
  });
});
