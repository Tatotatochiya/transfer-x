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
  STAFF_INVITATION:           "Team member joined",
  APPROVAL_REQUESTED:         "Approval requested",
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
  APPROVAL_DECIDED:         "text-success-text",
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

  const colour = TYPE_COLOURS[notification.type] ?? "text-text-secondary";

  return (
    <div
      onClick={handleClick}
      className={`flex items-start gap-3 px-4 py-3 transition-colors ${
        notification.link ? "cursor-pointer hover:bg-surface-inset" : ""
      } ${!notification.is_read ? "bg-surface" : "bg-surface-quiet"}`}
    >
      {/* Unread dot */}
      <div className="mt-1.5 shrink-0">
        {!notification.is_read ? (
          <div className="h-2 w-2 rounded-full bg-success" />
        ) : (
          <div className="h-2 w-2 rounded-full bg-transparent" />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold ${colour}`}>
            {TYPE_LABELS[notification.type] ?? notification.type}
          </span>
          <span className="text-[10px] text-text-muted">
            {formatDateTime(notification.created_at)}
          </span>
        </div>
        <p className="mt-0.5 text-sm text-text-secondary">{notification.message}</p>
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
              className="text-sm text-text-muted hover:text-text transition-colors"
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
          <div className="rounded-xl ring-1 ring-border overflow-hidden divide-y divide-rule-faint">
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
