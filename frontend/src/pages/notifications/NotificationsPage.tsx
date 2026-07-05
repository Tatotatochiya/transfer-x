import { useNavigate, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Notification, Paginated, UnreadCount } from "../../types/api";
import type { NotificationType } from "../../types/enums";
import { useState } from "react";
import Button from "../../components/ui/Button";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { formatDateTime } from "../../lib/utils";

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
};

const TYPE_COLOURS: Record<NotificationType, string> = {
  OUTBID:               "text-red-400",
  OFFER_RECEIVED:       "text-sky-400",
  OFFER_ACCEPTED:       "text-emerald-400",
  OFFER_REJECTED:       "text-red-400",
  OFFER_COUNTERED:      "text-amber-400",
  OFFER_WITHDRAWN:      "text-slate-400",
  OFFER_EXPIRING:       "text-amber-400",
  OFFER_MESSAGE:        "text-violet-400",
  AUCTION_BID_RECEIVED: "text-sky-400",
  AUCTION_ENDING:       "text-amber-400",
  AUCTION_BID_ACCEPTED: "text-emerald-400",
  DEAL_COMPLETED:           "text-emerald-400",
  DEAL_COLLAPSED:           "text-red-400",
  DEAL_SELL_ON:             "text-amber-400",
  DEAL_AGENT_INVITED:       "text-purple-400",
  DEAL_PERSONAL_TERMS_SENT: "text-amber-400",
  PLAYER_AVAILABLE:         "text-slate-300",
  VERIFICATION_APPROVED:    "text-sky-400",
  VERIFICATION_REJECTED:    "text-red-400",
  REPRESENTATION_STARTED:   "text-purple-400",
  REPRESENTATION_REVOKED:   "text-red-400",
  PERSONAL_TERMS_DECISION:  "text-amber-400",
  INSTALMENT_DUE:           "text-amber-400",
  DEAL_CLAUSE_TRIGGERED:    "text-amber-400",
  NEGOTIATION_MESSAGE:      "text-violet-400",
  CLIENT_ALERT:             "text-sky-400",
};

// ── Row component ─────────────────────────────────────────────────────────────

function NotificationRow({
  notification, dateRange, page,
}: { notification: Notification; dateRange: DateRange; page: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const listKey = ["notifications", { ...dateRange, page }] as const;

  const markReadMutation = useMutation({
    mutationFn: () =>
      api
        .post<Notification>(`/notifications/${notification.id}/read`)
        .then((r) => r.data),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: listKey });
      const prevList = queryClient.getQueryData<Paginated<Notification>>(listKey);
      const prevCount = queryClient.getQueryData<UnreadCount>(["notifications", "unread-count"]);
      if (prevList) {
        queryClient.setQueryData<Paginated<Notification>>(listKey, {
          ...prevList,
          items: prevList.items.map((n) =>
            n.id === notification.id ? { ...n, is_read: true } : n
          ),
        });
      }
      if (prevCount && prevCount.count > 0) {
        queryClient.setQueryData<UnreadCount>(["notifications", "unread-count"], {
          count: prevCount.count - 1,
        });
      }
      return { prevList, prevCount };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prevList) queryClient.setQueryData(listKey, ctx.prevList);
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

  const colour = TYPE_COLOURS[notification.type] ?? "text-slate-300";

  return (
    <div
      onClick={handleClick}
      className={`flex items-start gap-3 px-4 py-3 transition-colors ${
        notification.link ? "cursor-pointer hover:bg-slate-800/60" : ""
      } ${!notification.is_read ? "bg-slate-900" : "bg-slate-900/40"}`}
    >
      {/* Unread dot */}
      <div className="mt-1.5 shrink-0">
        {!notification.is_read ? (
          <div className="h-2 w-2 rounded-full bg-emerald-500" />
        ) : (
          <div className="h-2 w-2 rounded-full bg-transparent" />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold ${colour}`}>
            {TYPE_LABELS[notification.type] ?? notification.type}
          </span>
          <span className="text-[10px] text-slate-500">
            {formatDateTime(notification.created_at)}
          </span>
        </div>
        <p className="mt-0.5 text-sm text-slate-300">{notification.message}</p>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery<Paginated<Notification>>({
    queryKey: ["notifications", { ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<Notification>>("/notifications", {
          params: {
            page,
            page_size: 30,
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
  });

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

  const { data: unreadCount } = useQuery<UnreadCount>({
    queryKey: ["notifications", "unread-count"],
    queryFn: () =>
      api.get<UnreadCount>("/notifications/unread-count").then((r) => r.data),
  });

  const markAllMutation = useMutation({
    mutationFn: () =>
      api.post("/notifications/read-all").then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

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
              to="/account"
              className="text-sm text-slate-400 hover:text-white transition-colors"
            >
              Preferences
            </Link>
            {unreadCount && unreadCount.count > 0 && (
              <Button
                variant="secondary"
                size="sm"
                loading={markAllMutation.isPending}
                onClick={() => markAllMutation.mutate()}
              >
                Mark all as read
              </Button>
            )}
          </div>
        }
      />

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} />
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState title="No notifications" body="You're all caught up." />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="rounded-xl ring-1 ring-white/[0.08] overflow-hidden divide-y divide-white/[0.04]">
            {data.items.map((n) => (
              <NotificationRow key={n.id} notification={n} dateRange={dateRange} page={page} />
            ))}
          </div>

          <Pagination
            page={data.page}
            total={data.total}
            pageSize={data.page_size}
            onChange={setPage}
          />
        </>
      )}
    </div>
  );
}
