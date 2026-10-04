import { create } from "zustand";

import { API_BASE_URL } from "../lib/api";

/** Daily rates for the "≈ €21.0m" estimates next to £ amounts. Display only:
 *  every amount is stored and agreed in pounds (backend app/fx/service.py). */
interface FxState {
  rates: Record<string, number> | null;
  asOf: string | null;
  source: "ECB" | "fallback" | null;
  loading: boolean;
  load: () => Promise<void>;
}

export const useFxStore = create<FxState>()((set, get) => ({
  rates: null,
  asOf: null,
  source: null,
  loading: false,
  load: async () => {
    if (get().rates || get().loading) return;
    set({ loading: true });
    try {
      const resp = await fetch(`${API_BASE_URL}/fx/rates`);
      if (resp.ok) {
        const body = await resp.json();
        set({ rates: body.rates, asOf: body.as_of, source: body.source });
      }
    } catch {
      // No estimate is better than a wrong one: amounts still show in £.
    } finally {
      set({ loading: false });
    }
  },
}));
