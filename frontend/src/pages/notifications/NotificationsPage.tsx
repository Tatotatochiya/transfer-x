import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Notification, Paginated, UnreadCount } from "../../types/api";
import type { NotificationType } from "../../types/enums";
import { useEffect, useState } from "react";
import Button from "../../components/ui/Button";
import DateRangeFilter, { type DateRange } from "../../components/ui/DateRangeFilter";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { formatDate, formatDateTime } from "../../lib/utils";
import ClubLink from "../../components/ui/ClubLink";
import PlayerLink from "../../components/ui/PlayerLink";
import { ChasedBadge } from "../../components/transfer/ReminderBadges";
import Badge from "../../components/ui/Badge";

// ── Notification type labels + colours ───────────────────────────────────────

const TYPE_LABELS: Record<NotificationType, string> = {
  OUTBID:               "Outbid",
  OFFER_RECEIVED:       "Offer received",
  OFFER_ACCEPTED:       "Offer accepted",
  OFFER_REJECTED:       "Offer rejected",
  OFFER_COUNTERED:      "Counter offer",
  OFFER_WITHDRAWN:      "Offer withdrawn",
  OFFER_EXPIRING:       "Offer expiring",
  OFFER_MESSAGE:        "New message",
  AUCTION_BID_RECEIVED: "Bid received",
  AUCTION_ENDING:       "Auction ending soon",
  AUCTION_BID_ACCEPTED: "Auction bid accepted",
  DEAL_COMPLETED:             "Deal completed",
  DEAL_COLLAPSED:             "Deal collapsed",
  DEAL_SELL_ON:               "Sell-on clause triggered",
  DEAL_AGENT_INVITED:         "Agent invited",
  DEAL_PERSONAL_TERMS_SENT:   "Personal terms sent",
  PLAYER_AVAILABLE:           "Player available",
  VERIFICATION_APPROVED:      "Verification approved",
  VERIFICATION_REJECTED:      "Verification rejected",
  REPRESENTATION_STARTED:     "New representation",
  REPRESENTATION_REVOKED:     "Representation ended",
  PERSONAL_TERMS_DECISION:    "Personal terms decision",
  INSTALMENT_DUE:             "Instalment due",
  DEAL_CLAUSE_TRIGGERED:      "Clause triggered",
  NEGOTIATION_MESSAGE:        "New negotiation message",
  CLIENT_ALERT:               "Client alert",
  STAFF_INVITATION:           "Team member joined",
  APPROVAL_REQUESTED:         "Approval requested",
  LOAN_STARTED:               "Loan started",
  LOAN_ENDING_SOON:           "Loan ending soon",
  LOAN_ENDED:                 "Loan ended",
  LOAN_RECALLED:              "Player recalled",
  LOAN_CONVERTED:             "Loan becoming permanent",
  DAILY_DIGEST:               "Daily summary",
  DEAL_PAPERWORK:             "Paperwork",
  ENQUIRY_RECEIVED:           "Enquiry received",
  ENQUIRY_REPLIED:            "Enquiry reply",
  LITE_QUESTION:              "Question from your team",
  REGISTRATION_UPDATED:       "Squad updated",
  DEADLINE_DAY:               "Deadline day",
  REAL_WORLD_MOVES:           "Moved in real life",
  MOVE_REMINDER:              "Reminder",
  MOVE_ESCALATED:             "Still waiting on you",
  MOVE_STALLED:               "Transfer stuck",
  APPROVAL_DECIDED:           "Approval decided",
};

// Folded onto the app's 7-hue semantic token vocabulary (danger/success/
// warning/accent/muted/role-club/role-agent) — no per-type hues invented.
const TYPE_COLOURS: Record<NotificationType, string> = {
  OUTBID:               "text-danger-text",
  OFFER_RECEIVED:       "text-accent",
  OFFER_ACCEPTED:       "text-success-text",
  OFFER_REJECTED:       "text-danger-text",
  OFFER_COUNTERED:      "text-warning-text",
  OFFER_WITHDRAWN:      "text-text-muted",
  OFFER_EXPIRING:       "text-warning-text",
  OFFER_MESSAGE:        "text-role-agent-text",
  AUCTION_BID_RECEIVED: "text-accent",
  AUCTION_ENDING:       "text-warning-text",
  AUCTION_BID_ACCEPTED: "text-success-text",
  DEAL_COMPLETED:           "text-success-text",
  DEAL_COLLAPSED:           "text-danger-text",
  DEAL_SELL_ON:             "text-warning-text",
  DEAL_AGENT_INVITED:       "text-role-agent-text",
  DEAL_PERSONAL_TERMS_SENT: "text-warning-text",
  PLAYER_AVAILABLE:         "text-text-secondary",
  VERIFICATION_APPROVED:    "text-accent",
  VERIFICATION_REJECTED:    "text-danger-text",
  REPRESENTATION_STARTED:   "text-role-agent-text",
  REPRESENTATION_REVOKED:   "text-danger-text",
  PERSONAL_TERMS_DECISION:  "text-warning-text",
  INSTALMENT_DUE:           "text-warning-text",
  DEAL_CLAUSE_TRIGGERED:    "text-warning-text",
  NEGOTIATION_MESSAGE:      "text-role-agent-text",
  CLIENT_ALERT:             "text-accent",
  STAFF_INVITATION:         "text-role-club-text",
  APPROVAL_REQUESTED:       "text-warning-text",
  LOAN_STARTED:             "text-accent",
  LOAN_ENDING_SOON:         "text-warning-text",
  LOAN_ENDED:               "text-text-secondary",
  LOAN_RECALLED:            "text-warning-text",
  LOAN_CONVERTED:           "text-accent",
  DAILY_DIGEST:             "text-text-secondary",
  DEAL_PAPERWORK:           "text-accent",
  ENQUIRY_RECEIVED:         "text-accent",
  ENQUIRY_REPLIED:          "text-text-secondary",
  LITE_QUESTION:            "text-text-secondary",
  REGISTRATION_UPDATED:     "text-warning-text",
  DEADLINE_DAY:             "text-danger-text",
  REAL_WORLD_MOVES:         "text-warning-text",
  MOVE_REMINDER:            "text-danger-text",
  MOVE_ESCALATED:           "text-danger-text",
  MOVE_STALLED:             "text-warning-text",
  APPROVAL_DECIDED:         "text-success-text",
};

// ── Filters (kept in the URL) ────────────────────────────────────────────────

const PAGE_SIZE = 30;
const LIST_KEY = ["notifications", "list"] as const;

const TIERS = [
  { key: "YOUR_MOVE", label: "Your move" },
  { key: "HEADS_UP", label: "Heads-up" },
  { key: "FYI", label: "For your information" },
] as const;

const CATEGORIES = [
  { key: "offers", label: "Offers" },
  { key: "deals", label: "Deals" },
  { key: "reminders", label: "Reminders" },
  { key: "loans", label: "Loans" },
  { key: "squad", label: "Squad" },
  { key: "team", label: "Team" },
] as const;

interface Filters {
  q: string;
  unread: boolean;
  tier: string | null;
  category: string | null;
  player: { id: string; name: string } | null;
  club: { id: string; name: string } | null;
  dateFrom: string;
  dateTo: string;
}

function readFilters(p: URLSearchParams): Filters {
  const subject = (id: string, name: string) => (p.get(id) ? { id: p.get(id)!, name: p.get(name) ?? "" } : null);
  return {
    q: p.get("q") ?? "",
    unread: p.get("unread") === "1",
    tier: TIERS.some((t) => t.key === p.get("tier")) ? p.get("tier") : null,
    category: CATEGORIES.some((c) => c.key === p.get("category")) ? p.get("category") : null,
    player: subject("player", "player_name"),
    club: subject("club", "club_name"),
    dateFrom: p.get("from") ?? "",
    dateTo: p.get("to") ?? "",
  };
}

/** The API's query parameters for these filters (the list and "Mark these read"). */
function apiParams(f: Filters): Record<string, string | boolean> {
  return {
    ...(f.q.trim() && { q: f.q.trim() }),
    ...(f.unread && { unread: true }),
    ...(f.tier && { tier: f.tier }),
    ...(f.category && { category: f.category }),
    ...(f.player && { player_id: f.player.id }),
    ...(f.club && { club_id: f.club.id }),
    ...(f.dateFrom && { date_from: f.dateFrom }),
    ...(f.dateTo && { date_to: f.dateTo }),
  };
}

const isFiltered = (f: Filters) =>
  !!(f.q.trim() || f.unread || f.tier || f.category || f.player || f.club || f.dateFrom || f.dateTo);

/** "Today", "Yesterday", "Earlier this week", then the date. */
export function dayLabel(iso: string, now = new Date()): string {
  const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((start(now) - start(new Date(iso))) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Earlier this week";
  return formatDate(iso);
}

const CHIP = "inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-small font-semibold ring-1";
const CHIP_ON = "bg-accent-bg text-text ring-accent-ring";
const CHIP_OFF = "bg-surface text-text-secondary ring-input-border hover:text-text";

function FilterIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M2.5 3.5h11l-4.2 5v4l-2.6 1.2V8.5z" strokeLinejoin="round" />
    </svg>
  );
}

// ── Row component ─────────────────────────────────────────────────────────────

function NotificationRow({ notification, onFilterPlayer, onFilterClub }: {
  notification: Notification;
  onFilterPlayer: (p: { id: string; name: string }) => void;
  onFilterClub: (c: { id: string; name: string }) => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const markReadMutation = useMutation({
    mutationFn: () =>
      api
        .post<Notification>(`/notifications/${notification.id}/read`)
        .then((r) => r.data),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: LIST_KEY });
      const prevLists = queryClient.getQueriesData<InfiniteData<Paginated<Notification>>>({ queryKey: LIST_KEY });
      const prevCount = queryClient.getQueryData<UnreadCount>(["notifications", "unread-count"]);
      queryClient.setQueriesData<InfiniteData<Paginated<Notification>>>({ queryKey: LIST_KEY }, (old) => old && ({
        ...old,
        pages: old.pages.map((pg) => ({
          ...pg, items: pg.items.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)),
        })),
      }));
      if (prevCount && prevCount.count > 0) {
        queryClient.setQueryData<UnreadCount>(["notifications", "unread-count"], {
          count: prevCount.count - 1,
        });
      }
      return { prevLists, prevCount };
    },
    onError: (_err, _vars, ctx) => {
      ctx?.prevLists.forEach(([key, data]) => queryClient.setQueryData(key, data));
      if (ctx?.prevCount) queryClient.setQueryData(["notifications", "unread-count"], ctx.prevCount);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  function handleClick() {
    if (!notification.is_read) {
      markReadMutation.mutate();
    }
    if (notification.link) {
      navigate(notification.link);
    }
  }

  const colour = TYPE_COLOURS[notification.type] ?? "text-text-secondary";
  const subjectFilter = (label: string, onClick: () => void) => (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted hover:bg-surface-inset hover:text-text"
    >
      <FilterIcon />
    </button>
  );

  return (
    <li
      onClick={handleClick}
      className={`flex items-start gap-3 px-4 py-3 transition-colors ${
        notification.link ? "cursor-pointer hover:bg-surface-inset" : ""
      } ${!notification.is_read ? "bg-surface" : "bg-surface-quiet"}`}
    >
      {/* Unread dot */}
      <div className="mt-1.5 shrink-0">
        {!notification.is_read ? (
          <div className="h-2 w-2 rounded-full bg-success" aria-label="Unread" />
        ) : (
          <div className="h-2 w-2 rounded-full bg-transparent" />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-caption font-semibold ${colour}`}>
            {TYPE_LABELS[notification.type] ?? notification.type}
          </span>
          {notification.type === "MOVE_ESCALATED" && <ChasedBadge escalated />}
          {notification.type === "MOVE_STALLED" && <Badge variant="warning">Escalated</Badge>}
          <span className="text-small text-text-muted">
            {formatDateTime(notification.created_at)}
          </span>
        </div>
        {/* The push wording when there is one (who, how much, by when), else
            the plain message. */}
        {notification.title ? (
          <>
            <p className="mt-0.5 text-body font-medium text-text">{notification.title}</p>
            {notification.body && <p className="text-body text-text-secondary">{notification.body}</p>}
          </>
        ) : (
          <p className="mt-0.5 text-body text-text-secondary">{notification.message}</p>
        )}
        {(notification.player || notification.club) && (
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption font-medium text-text">
            {notification.player && (
              <span className="inline-flex items-center gap-0.5">
                <PlayerLink id={notification.player.id} name={notification.player.name} photoUrl={notification.player.image_url} />
                {subjectFilter(`Show only notifications about ${notification.player.name}`,
                  () => onFilterPlayer({ id: notification.player!.id, name: notification.player!.name }))}
              </span>
            )}
            {notification.club && (
              <span className="inline-flex items-center gap-0.5">
                <ClubLink id={notification.club.id} name={notification.club.name} crestUrl={notification.club.image_url} />
                {subjectFilter(`Show only notifications about ${notification.club.name}`,
                  () => onFilterClub({ id: notification.club!.id, name: notification.club!.name }))}
              </span>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const [search, setSearch] = useState(filters.q);

  function update(change: (p: URLSearchParams) => void) {
    setParams((p) => { const n = new URLSearchParams(p); change(n); return n; }, { replace: true });
  }
  const set = (key: string, value: string | null) => update((p) => { if (value) p.set(key, value); else p.delete(key); });
  const setSubject = (key: "player" | "club", s: { id: string; name: string } | null) => update((p) => {
    if (s) { p.set(key, s.id); p.set(`${key}_name`, s.name); } else { p.delete(key); p.delete(`${key}_name`); }
  });

  // The search box writes ?q= once typing pauses.
  useEffect(() => {
    if (search === filters.q) return;
    const t = setTimeout(() => set("q", search.trim() || null), 300);
    return () => clearTimeout(t);
  }, [search]); // eslint-disable-line react-hooks/exhaustive-deps

  const query = apiParams(filters);
  const list = useInfiniteQuery<Paginated<Notification>>({
    queryKey: [...LIST_KEY, query],
    queryFn: ({ pageParam }) =>
      api.get<Paginated<Notification>>("/notifications", { params: { ...query, page: pageParam, page_size: PAGE_SIZE } })
        .then((r) => r.data),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
  });
  const items = list.data?.pages.flatMap((pg) => pg.items) ?? [];
  const total = list.data?.pages[0]?.total ?? 0;

  const { data: unreadCount } = useQuery<UnreadCount>({
    queryKey: ["notifications", "unread-count"],
    queryFn: () =>
      api.get<UnreadCount>("/notifications/unread-count").then((r) => r.data),
  });

  const filtered = isFiltered(filters);
  const markMutation = useMutation({
    mutationFn: () => api.post("/notifications/read-all", null, { params: filtered ? query : {} }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
  const unreadHere = items.some((n) => !n.is_read);
  const showMark = filtered ? unreadHere : !!unreadCount && unreadCount.count > 0;

  // Day headings over the loaded rows.
  const days: { label: string; rows: Notification[] }[] = [];
  for (const n of items) {
    const label = dayLabel(n.created_at);
    if (days.length === 0 || days[days.length - 1].label !== label) days.push({ label, rows: [] });
    days[days.length - 1].rows.push(n);
  }

  const dateRange: DateRange = { dateFrom: filters.dateFrom, dateTo: filters.dateTo };
  const clearAll = () => { setSearch(""); setParams(new URLSearchParams(), { replace: true }); };

  return (
    <div>
      <PageHeader
        title="Notifications"
        subtitle={
          unreadCount && unreadCount.count > 0
            ? `${unreadCount.count} unread`
            : "All caught up"
        }
        actions={
          <div className="flex items-center gap-2">
            <Link
              to="/account#notifications"
              className="text-body text-text-muted hover:text-text transition-colors"
            >
              Preferences
            </Link>
            {showMark && (
              <Button
                variant="secondary"
                size="sm"
                loading={markMutation.isPending}
                onClick={() => markMutation.mutate()}
              >
                {filtered ? "Mark these read" : "Mark all as read"}
              </Button>
            )}
          </div>
        }
      />

      <div className="mb-5 space-y-3">
        <div role="search" className="relative">
          <label htmlFor="notif-search" className="sr-only">Search notifications</label>
          <input
            id="notif-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search a player or club"
            className="w-full min-h-11 rounded-lg bg-surface px-3 text-input text-text ring-1 ring-input-border focus:outline-none focus:ring-accent sm:max-w-sm lg:min-h-10 lg:text-body"
          />
        </div>

        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-0.5 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0 [&::-webkit-scrollbar]:hidden">
          <button type="button" aria-pressed={filters.unread} onClick={() => set("unread", filters.unread ? null : "1")}
            className={`${CHIP} ${filters.unread ? CHIP_ON : CHIP_OFF}`}>
            Unread
          </button>
          <span aria-hidden className="mx-1 w-px shrink-0 self-stretch bg-rule" />
          <div role="radiogroup" aria-label="Whose move" className="flex gap-2">
            {TIERS.map((t) => (
              <button key={t.key} type="button" role="radio" aria-checked={filters.tier === t.key}
                onClick={() => set("tier", filters.tier === t.key ? null : t.key)}
                className={`${CHIP} ${filters.tier === t.key ? CHIP_ON : CHIP_OFF}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div role="radiogroup" aria-label="Category"
          className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-0.5 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0 [&::-webkit-scrollbar]:hidden">
          {CATEGORIES.map((c) => (
            <button key={c.key} type="button" role="radio" aria-checked={filters.category === c.key}
              onClick={() => set("category", filters.category === c.key ? null : c.key)}
              className={`${CHIP} ${filters.category === c.key ? CHIP_ON : CHIP_OFF}`}>
              {c.label}
            </button>
          ))}
        </div>

        {(filters.player || filters.club) && (
          <div className="flex flex-wrap gap-2">
            {filters.player && (
              <button type="button" onClick={() => setSubject("player", null)}
                aria-label={`Remove filter ${filters.player.name}`} className={`${CHIP} ${CHIP_ON}`}>
                {filters.player.name} <span aria-hidden>×</span>
              </button>
            )}
            {filters.club && (
              <button type="button" onClick={() => setSubject("club", null)}
                aria-label={`Remove filter ${filters.club.name}`} className={`${CHIP} ${CHIP_ON}`}>
                {filters.club.name} <span aria-hidden>×</span>
              </button>
            )}
          </div>
        )}

        <DateRangeFilter value={dateRange}
          onChange={(r) => update((p) => {
            if (r.dateFrom) p.set("from", r.dateFrom); else p.delete("from");
            if (r.dateTo) p.set("to", r.dateTo); else p.delete("to");
          })} />
      </div>

      {list.isLoading && (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      )}

      {list.data && items.length === 0 && (
        filtered ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-small text-text-secondary">
            No notifications match these filters.{" "}
            <button type="button" onClick={clearAll} className="font-semibold text-accent hover:underline">Clear filters</button>
          </div>
        ) : (
          <EmptyState title="No notifications" body="You're all caught up." />
        )
      )}

      {items.length > 0 && (
        <div className="space-y-5">
          {days.map((d) => (
            <section key={d.label} aria-label={d.label}>
              <h2 className="mb-2 text-small font-semibold text-text-secondary">{d.label}</h2>
              <ul className="overflow-hidden rounded-xl ring-1 ring-border divide-y divide-rule-faint">
                {d.rows.map((n) => (
                  <NotificationRow key={n.id} notification={n}
                    onFilterPlayer={(p) => setSubject("player", p)} onFilterClub={(c) => setSubject("club", c)} />
                ))}
              </ul>
            </section>
          ))}
          <div className="flex flex-col items-center gap-1.5 pt-1">
            {list.hasNextPage && (
              <Button variant="secondary" loading={list.isFetchingNextPage} onClick={() => list.fetchNextPage()}>
                Show {Math.min(PAGE_SIZE, total - items.length)} more
              </Button>
            )}
            <p className="text-small text-text-muted">Showing {items.length} of {total}</p>
          </div>
        </div>
      )}
    </div>
  );
}
