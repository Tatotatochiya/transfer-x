import { Link } from "react-router-dom";

import Spinner from "../../components/ui/Spinner";
import { useClubDashboard } from "../../hooks/useClubDashboard";
import { liteMoney } from "../../lib/liteMoney";
import type { DashboardItem } from "../../types/api";
import FallbackImage from "../../components/ui/FallbackImage";

const KIND_WORD: Record<DashboardItem["kind"], string> = {
  offer: "Offer", approval: "Your approval", deal: "Transfer", enquiry: "Enquiry",
};

function deadlineText(iso: string | null): string | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "Due now";
  const days = Math.floor(ms / 86_400_000);
  return days >= 1 ? `${days} day${days === 1 ? "" : "s"} left to answer` : "Less than a day left";
}

/**
 * Answer offers (README "Screen 1" destination): what is waiting, straight
 * from the Dashboard's list. Offers open as Lite action cards (L4); the rest
 * still open their full-app pages.
 */
export default function LiteOffersPage() {
  const { data, isLoading } = useClubDashboard(true);
  const items = data?.waiting_on_you ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lite-title font-extrabold tracking-[-0.02em] text-text sm:text-lite-title-lg">Answer offers</h1>
        <p className="mt-1 text-lite-section text-text-secondary">
          {items.length ? "These are waiting for you. Tap one to open it." : ""}
        </p>
      </div>
      {isLoading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : items.length === 0 ? (
        <p className="rounded-3xl bg-surface px-8 py-10 text-lite-section text-text ring-1 ring-border">
          Nothing needs you today.
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {items.map((item) => {
            const due = deadlineText(item.deadline);
            return (
              <li key={`${item.kind}-${item.id}`}>
                <Link
                  to={item.kind === "offer" ? `/lite/offers/${item.id}` : item.link}
                  className="flex flex-wrap items-center gap-4 rounded-3xl bg-surface px-7 py-6 no-underline ring-1 ring-border transition-transform hover:ring-accent active:scale-[0.99]"
                >
                  {/* His photo; the card it opens links to his profile. */}
                  {item.player_name && (
                    <FallbackImage src={item.player_photo_url} name={item.player_name} sizeClass="h-16 w-16 text-lite-headline" colorClass="bg-surface-inset text-text-muted" className="font-extrabold" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-danger-bg px-3 py-0.5 text-lite-caption font-semibold text-danger-text">
                        {KIND_WORD[item.kind]}
                      </span>
                      <span className="rounded-full bg-accent-bg px-3 py-0.5 text-lite-caption font-bold text-accent">Your move</span>
                    </span>
                    <span className="mt-2 block text-lite-headline font-extrabold text-text">
                      {item.player_name ?? "—"}{item.club_name ? ` · ${item.club_name}` : ""}
                    </span>
                    <span className="mt-1 block text-lite-body text-text-secondary">
                      {item.reason}
                      {item.amount != null ? ` · ${liteMoney(Number(item.amount))}` : ""}
                    </span>
                    {due && <span className="mt-1 block text-lite-caption font-semibold text-warning-text">{due}</span>}
                  </span>
                  <span className="flex min-h-[3.25rem] items-center rounded-xl bg-accent px-6 text-lite-body font-bold text-on-accent">
                    Open →
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
