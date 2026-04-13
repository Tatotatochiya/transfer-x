/**
 * Connects to the backend WebSocket endpoint and invalidates TanStack Query
 * cache keys when the server pushes an event.
 *
 * Auth: access token is passed as ?token=<jwt> query param (WS doesn't support
 * custom headers in the browser).
 *
 * Reconnect: exponential backoff capped at 30s.
 */

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";

const BASE_URL = import.meta.env.VITE_WS_URL ?? "";  // falls back to same host
const MAX_BACKOFF_MS = 30_000;

function wsUrl(token: string): string {
  if (BASE_URL) {
    return `${BASE_URL}/ws?token=${token}`;
  }
  // Derive from current page host (works with the Vite dev proxy too)
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/ws?token=${token}`;
}

type WsEvent =
  | { type: "SALE_UPDATED"; id: string }
  | { type: "BID_PLACED"; sale_id: string }
  | { type: "OFFER_UPDATED"; id: string }
  | { type: "DEAL_UPDATED"; id: string }
  | { type: "NOTIFICATION" };

export function useWebSocket(): void {
  const queryClient = useQueryClient();
  const { accessToken } = useAuthStore();
  const socketRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef<number>(1_000);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  useEffect(() => {
    if (!accessToken) return;

    unmountedRef.current = false;

    function connect() {
      if (unmountedRef.current) return;

      const ws = new WebSocket(wsUrl(accessToken!));
      socketRef.current = ws;

      ws.onopen = () => {
        backoffRef.current = 1_000; // reset backoff on successful connect
      };

      ws.onmessage = (event) => {
        let msg: WsEvent;
        try {
          msg = JSON.parse(event.data) as WsEvent;
        } catch {
          return;
        }

        switch (msg.type) {
          case "BID_PLACED":
            queryClient.invalidateQueries({ queryKey: ["sales", msg.sale_id] });
            queryClient.invalidateQueries({ queryKey: ["sales", msg.sale_id, "bids"] });
            queryClient.invalidateQueries({ queryKey: ["sales", msg.sale_id, "order-book"] });
            queryClient.invalidateQueries({ queryKey: ["offers", "competition"] });
            queryClient.invalidateQueries({ queryKey: ["dashboard"] });
            break;

          case "SALE_UPDATED":
            queryClient.invalidateQueries({ queryKey: ["sales"] }); // prefix — covers lists, detail, bids, order-book
            queryClient.invalidateQueries({ queryKey: ["offers", "competition"] });
            queryClient.invalidateQueries({ queryKey: ["dashboard"] });
            break;

          case "OFFER_UPDATED":
            queryClient.invalidateQueries({ queryKey: ["offers", msg.id] });
            queryClient.invalidateQueries({ queryKey: ["offers", "received"] });
            queryClient.invalidateQueries({ queryKey: ["offers", "sent"] });
            queryClient.invalidateQueries({ queryKey: ["offers", "competition"] });
            queryClient.invalidateQueries({ queryKey: ["dashboard"] });
            break;

          case "DEAL_UPDATED":
            queryClient.invalidateQueries({ queryKey: ["deals", msg.id] });
            queryClient.invalidateQueries({ queryKey: ["deals"] });
            queryClient.invalidateQueries({ queryKey: ["dashboard"] });
            break;

          case "NOTIFICATION":
            queryClient.invalidateQueries({ queryKey: ["notifications", "unread-count"] });
            queryClient.invalidateQueries({ queryKey: ["notifications"] });
            break;
        }
      };

      ws.onclose = (event) => {
        socketRef.current = null;
        // 4001 = auth failure — don't reconnect
        if (unmountedRef.current || event.code === 4001) return;

        timeoutRef.current = setTimeout(() => {
          backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
          connect();
        }, backoffRef.current);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      socketRef.current?.close();
    };
  }, [accessToken, queryClient]);
}
