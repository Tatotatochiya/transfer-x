import { useEffect, useState } from "react";
import { formatDeadline, type DeadlineResult } from "../lib/utils";

export function useDeadlineCountdown(deadline: string | null | undefined): DeadlineResult {
  const [result, setResult] = useState<DeadlineResult>(() => formatDeadline(deadline));

  useEffect(() => {
    if (!deadline) return;

    // Update immediately then on every tick
    setResult(formatDeadline(deadline));
    const timer = setInterval(() => setResult(formatDeadline(deadline)), 1000);
    return () => clearInterval(timer);
  }, [deadline]);

  return result;
}
