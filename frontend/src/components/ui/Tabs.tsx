export interface TabItem {
  key: string;
  label: string;
}

interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}

/**
 * Underline tab bar — replaces the hand-rolled tab-state pattern duplicated
 * across OfferInboxPage, DealListPage, MySalesPage, MyClubPage, and others.
 * Controlled: the caller owns the active key.
 */
export default function Tabs({ tabs, active, onChange, className = "" }: TabsProps) {
  return (
    <div className={`flex gap-1 border-b border-rule ${className}`} role="tablist">
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.key)}
            className={`min-h-11 lg:min-h-0 border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
              isActive
                ? "border-accent text-accent"
                : "border-transparent text-text-muted hover:text-text-secondary"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
