/**
 * usePageTracking — tracks page views and time-on-page via react-router location.
 *
 * Call once in GlobalSetup. On each navigation:
 *  - fires PAGE_LEAVE for the previous path with ms elapsed
 *  - fires PAGE_VIEW for the new path
 */

import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { trackPageLeave, trackPageView } from "../lib/analytics";

export function usePageTracking(): void {
  const location = useLocation();
  const prevPath = useRef<string | null>(null);
  const enterTime = useRef<number>(Date.now());

  useEffect(() => {
    const currentPath = location.pathname;

    // Fire leave for previous page
    if (prevPath.current !== null && prevPath.current !== currentPath) {
      const duration_ms = Date.now() - enterTime.current;
      trackPageLeave(prevPath.current, duration_ms);
    }

    // Fire view for current page
    trackPageView(currentPath, prevPath.current ?? undefined);

    prevPath.current = currentPath;
    enterTime.current = Date.now();
  }, [location.pathname]);

  // Fire leave on tab close / component unmount
  useEffect(() => {
    return () => {
      if (prevPath.current !== null) {
        const duration_ms = Date.now() - enterTime.current;
        trackPageLeave(prevPath.current, duration_ms);
      }
    };
  }, []);
}
