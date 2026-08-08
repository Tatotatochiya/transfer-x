import { useCallback, useRef, useState } from "react";

import { API_BASE_URL } from "../lib/api";
import { useAuthStore } from "../store/auth";
import type { SquadAnalysisResponse } from "../types/api";

type StreamState = "idle" | "streaming" | "done" | "error";

interface UseStreamingSquadAnalysisReturn {
  state: StreamState;
  streamText: string;
  result: SquadAnalysisResponse | null;
  error: string | null;
  start: (forceRefresh?: boolean) => void;
  reset: () => void;
}

export function useStreamingSquadAnalysis(): UseStreamingSquadAnalysisReturn {
  const { accessToken } = useAuthStore();
  const [state, setState] = useState<StreamState>("idle");
  const [streamText, setStreamText] = useState("");
  const [result, setResult] = useState<SquadAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState("idle");
    setStreamText("");
    setResult(null);
    setError(null);
  }, []);

  const start = useCallback(
    async (forceRefresh = false) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState("streaming");
      setStreamText("");
      setResult(null);
      setError(null);

      const url = `${API_BASE_URL}/ai/squad-analysis/stream${forceRefresh ? "?force_refresh=true" : ""}`;

      try {
        const response = await fetch(url, {
          signal: controller.signal,
          headers: { Authorization: `Bearer ${accessToken}` },
        });

        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail ?? `HTTP ${response.status}`);
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const payload = line.slice(6);
            if (payload === "[DONE]") {
              setState("done");
              return;
            }
            try {
              const event = JSON.parse(payload) as {
                type: "chunk" | "done" | "error";
                content?: string;
                result?: SquadAnalysisResponse;
                detail?: string;
              };
              if (event.type === "chunk" && event.content) {
                setStreamText((t) => t + event.content);
              } else if (event.type === "done" && event.result) {
                setResult(event.result);
              } else if (event.type === "error") {
                throw new Error(event.detail ?? "Stream error");
              }
            } catch {
              // Ignore malformed lines
            }
          }
        }
        setState("done");
      } catch (err: unknown) {
        if ((err as { name?: string }).name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Unknown error");
        setState("error");
      }
    },
    [accessToken],
  );

  return { state, streamText, result, error, start, reset };
}
