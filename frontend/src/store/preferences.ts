import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Currency = "GBP" | "EUR" | "USD";
export type MarketView = "grid" | "list";
export type DateFormat = "relative" | "absolute";

interface PreferencesState {
  currency: Currency;
  defaultMarketView: MarketView;
  dateFormat: DateFormat;
  setCurrency: (v: Currency) => void;
  setDefaultMarketView: (v: MarketView) => void;
  setDateFormat: (v: DateFormat) => void;
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      currency: "GBP",
      defaultMarketView: "grid",
      dateFormat: "absolute",
      setCurrency: (currency) => set({ currency }),
      setDefaultMarketView: (defaultMarketView) => set({ defaultMarketView }),
      setDateFormat: (dateFormat) => set({ dateFormat }),
    }),
    { name: "transferx-prefs" }
  )
);
