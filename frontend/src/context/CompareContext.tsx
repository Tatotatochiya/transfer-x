import { createContext, useCallback, useContext, useState } from "react";

interface CompareContextValue {
  compareIds: string[];
  toggle: (id: string) => void;
  clear: () => void;
  has: (id: string) => boolean;
}

const CompareContext = createContext<CompareContextValue | null>(null);

export function CompareProvider({ children }: { children: React.ReactNode }) {
  const [compareIds, setCompareIds] = useState<string[]>([]);

  const toggle = useCallback((id: string) => {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id]; // slide window: drop oldest, add new
      return [...prev, id];
    });
  }, []);

  const clear = useCallback(() => setCompareIds([]), []);
  const has = useCallback((id: string) => compareIds.includes(id), [compareIds]);

  return (
    <CompareContext.Provider value={{ compareIds, toggle, clear, has }}>
      {children}
    </CompareContext.Provider>
  );
}

export function useCompare() {
  const ctx = useContext(CompareContext);
  if (!ctx) throw new Error("useCompare must be used inside CompareProvider");
  return ctx;
}
