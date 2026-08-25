import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { NotificationPreferencesResponse } from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { getApiError } from "../../lib/utils";

function MiniToggle({
  value, disabled, onChange, label,
}: { value: boolean; disabled: boolean; onChange: () => void; label: string }) {
  return (
    <button
      disabled={disabled}
      onClick={onChange}
      aria-label={label}
      title={label}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-50 ${
        value ? "bg-success" : "bg-border"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow ring-0 transition-transform ${
          value ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

const TYPE_LABELS: Record<string, string> = {
  OUTBID:               "Outbid on an auction",
  OFFER_RECEIVED:       "Offer received",
  OFFER_ACCEPTED:       "Offer accepted",
  OFFER_REJECTED:       "Offer rejected",
  OFFER_COUNTERED:      "Counter-offer received",
  OFFER_WITHDRAWN:      "Offer withdrawn by other party",
  OFFER_EXPIRING:       "Offer expiring soon",
  OFFER_MESSAGE:        "New message in a negotiation",
  AUCTION_BID_RECEIVED: "Bid received on your auction",
  AUCTION_ENDING:       "Auction ending soon",
  AUCTION_BID_ACCEPTED: "Your auction bid accepted",
  DEAL_COMPLETED:       "Deal completed",
  DEAL_COLLAPSED:       "Deal collapsed",
  PLAYER_AVAILABLE:     "Shortlisted player becomes available",
  VERIFICATION_APPROVED: "Verification request approved",
  VERIFICATION_REJECTED: "Verification request rejected",
  REPRESENTATION_STARTED: "An agent starts representing you",
  REPRESENTATION_REVOKED: "A player ends your representation mandate",
  PERSONAL_TERMS_DECISION: "Player accepts/declines personal terms",
  INSTALMENT_DUE: "Deal instalment due or overdue",
  DEAL_CLAUSE_TRIGGERED: "Add-on/bonus clause triggered",
  NEGOTIATION_MESSAGE: "New negotiation message or deal comment",
  CLIENT_ALERT: "Client alert (contract expiry, valuation change, club interest)",
  STAFF_INVITATION: "A team member accepts your invitation",
  APPROVAL_REQUESTED: "A spending approval needs your decision",
  LOAN_STARTED: "A loan you agreed has started",
  LOAN_ENDING_SOON: "A loan is ending within two weeks",
  LOAN_ENDED: "A loan has ended and the player has returned",
  LOAN_RECALLED: "A parent club has recalled their player early",
  LOAN_CONVERTED: "A loan is turning into a permanent transfer",
  APPROVAL_DECIDED: "Your spending request is decided",
};

const TYPE_GROUPS: { label: string; types: string[] }[] = [
  {
    label: "Auctions",
    types: ["AUCTION_BID_RECEIVED", "AUCTION_ENDING", "AUCTION_BID_ACCEPTED", "OUTBID"],
  },
  {
    label: "Offers",
    types: ["OFFER_RECEIVED", "OFFER_ACCEPTED", "OFFER_REJECTED", "OFFER_COUNTERED", "OFFER_WITHDRAWN", "OFFER_EXPIRING", "OFFER_MESSAGE"],
  },
  {
    label: "Deals",
    types: ["DEAL_COMPLETED", "DEAL_COLLAPSED", "PERSONAL_TERMS_DECISION", "INSTALMENT_DUE", "DEAL_CLAUSE_TRIGGERED", "NEGOTIATION_MESSAGE"],
  },
  {
    label: "Scouting",
    types: ["PLAYER_AVAILABLE"],
  },
  {
    label: "Representation",
    types: ["REPRESENTATION_STARTED", "REPRESENTATION_REVOKED"],
  },
  {
    label: "Client intelligence",
    types: ["CLIENT_ALERT"],
  },
  {
    label: "Verification",
    types: ["VERIFICATION_APPROVED", "VERIFICATION_REJECTED"],
  },
  {
    label: "Team & approvals",
    types: ["STAFF_INVITATION", "APPROVAL_REQUESTED", "APPROVAL_DECIDED"],
  },
  {
    label: "Loans",
    types: ["LOAN_STARTED", "LOAN_ENDING_SOON", "LOAN_ENDED", "LOAN_RECALLED", "LOAN_CONVERTED"],
  },
];

export default function NotificationPreferencesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery<NotificationPreferencesResponse>({
    queryKey: ["notifications", "preferences"],
    queryFn: () =>
      api.get<NotificationPreferencesResponse>("/notifications/preferences").then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: ({ type, channel, value }: { type: string; channel: "enabled" | "email_enabled"; value: boolean }) =>
      api
        .patch<NotificationPreferencesResponse>(`/notifications/preferences/${type}`, { [channel]: value })
        .then((r) => r.data),
    onSuccess: (newData) => {
      queryClient.setQueryData(["notifications", "preferences"], newData);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
        Failed to load preferences.
      </div>
    );
  }

  const prefMap = Object.fromEntries(data.preferences.map((p) => [p.type, p]));

  return (
    <div>
      <button
        onClick={() => navigate("/notifications")}
        className="mb-6 flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
      >
        ← Back to notifications
      </button>

      <PageHeader
        title="Notification preferences"
        subtitle="Choose which notifications you want to receive"
      />

      <div className="space-y-6 max-w-xl">
        <div className="flex items-center justify-end gap-8 px-1 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          <span className="w-9 text-center">In-app</span>
          <span className="w-9 text-center">Email</span>
        </div>

        {TYPE_GROUPS.map((group) => (
          <Card key={group.label} noPadding>
            <div className="border-b border-rule px-5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                {group.label}
              </p>
            </div>
            <div className="divide-y divide-rule-faint">
              {group.types.map((type) => {
                const pref = prefMap[type];
                const enabled = pref?.enabled ?? true;
                const emailEnabled = pref?.email_enabled ?? true;
                const vars = mutation.variables as { type: string; channel: string } | undefined;
                const isPendingChannel = (channel: string) =>
                  mutation.isPending && vars?.type === type && vars?.channel === channel;
                return (
                  <div key={type} className="flex items-center justify-between px-5 py-3.5">
                    <span className="text-sm text-text">
                      {TYPE_LABELS[type] ?? type}
                    </span>
                    <div className="flex items-center gap-8">
                      <div className="w-9 flex justify-center">
                        <MiniToggle
                          value={enabled}
                          disabled={isPendingChannel("enabled")}
                          onChange={() => mutation.mutate({ type, channel: "enabled", value: !enabled })}
                          label={enabled ? `Disable in-app for ${type}` : `Enable in-app for ${type}`}
                        />
                      </div>
                      <div className="w-9 flex justify-center">
                        <MiniToggle
                          value={emailEnabled}
                          disabled={isPendingChannel("email_enabled")}
                          onChange={() => mutation.mutate({ type, channel: "email_enabled", value: !emailEnabled })}
                          label={emailEnabled ? `Disable email for ${type}` : `Enable email for ${type}`}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        ))}

        {mutation.isError && (
          <p className="text-sm text-danger-text">
            {getApiError(mutation.error, "Failed to save preference.")}
          </p>
        )}
      </div>
    </div>
  );
}
