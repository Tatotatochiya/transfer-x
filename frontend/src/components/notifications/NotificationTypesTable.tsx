import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { getApiError } from "../../lib/utils";
import type { NotificationPreferencesResponse } from "../../types/api";
import Card from "../ui/Card";
import Spinner from "../ui/Spinner";

/**
 * Every notification type, with a switch per channel: In-app, Email and
 * Push. FYI types are never pushed, so their Push switch is disabled
 * (docs/feature_spec/mobile-notifications §7.3, 5c).
 */

export function MiniToggle({
  value, disabled, onChange, label, title,
}: { value: boolean; disabled: boolean; onChange: () => void; label: string; title?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      disabled={disabled}
      onClick={onChange}
      aria-label={label}
      title={title ?? label}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50 ${
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

export const TYPE_LABELS: Record<string, string> = {
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
  SALE_REOPENED:        "A sale you bid on is open again after its deal collapsed",
  DEAL_SLA_BREACHED:    "A deal's paperwork is past its expected deadline",
  DEAL_PERSONAL_TERMS_SENT: "Personal terms sent for the player's answer",
  DEAL_SELL_ON:         "A sell-on clause pays out to you",
  DEAL_AGENT_INVITED:   "You are invited to negotiate a transfer",
  RELEASE_CLAUSE_TRIGGERED: "A club meets one of your players' release clauses",
  PLAYER_AVAILABLE:     "Shortlisted player becomes available",
  VERIFICATION_APPROVED: "Verification request approved",
  VERIFICATION_REJECTED: "Verification request rejected",
  REPRESENTATION_STARTED: "An agent starts representing you",
  REPRESENTATION_REVOKED: "A player ends your representation mandate",
  REPRESENTATION_EXPIRED: "A representation mandate expires",
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
  ENQUIRY_RECEIVED: "A club asks about one of your players",
  ENQUIRY_REPLIED: "A reply in one of your enquiries",
  DEAL_PAPERWORK: "The other club completes a paperwork step, or the paperwork is done",
  DAILY_DIGEST: "A morning email of what is waiting on you — sent only when something is",
  APPROVAL_DECIDED: "Your spending request is decided",
};

const TYPE_GROUPS: { label: string; types: string[] }[] = [
  // First: for a club that visits a few times a week, this one email is the
  // thing most likely to stop an offer expiring unseen.
  { label: "Daily summary", types: ["DAILY_DIGEST"] },
  { label: "Auctions", types: ["AUCTION_BID_RECEIVED", "AUCTION_ENDING", "AUCTION_BID_ACCEPTED", "OUTBID", "SALE_REOPENED"] },
  {
    label: "Offers",
    types: ["ENQUIRY_RECEIVED", "ENQUIRY_REPLIED", "OFFER_RECEIVED", "OFFER_ACCEPTED", "OFFER_REJECTED", "OFFER_COUNTERED", "OFFER_WITHDRAWN", "OFFER_EXPIRING", "OFFER_MESSAGE", "RELEASE_CLAUSE_TRIGGERED"],
  },
  {
    label: "Deals",
    types: ["DEAL_COMPLETED", "DEAL_COLLAPSED", "DEAL_PERSONAL_TERMS_SENT", "PERSONAL_TERMS_DECISION", "DEAL_PAPERWORK", "DEAL_SLA_BREACHED", "INSTALMENT_DUE", "DEAL_CLAUSE_TRIGGERED", "DEAL_SELL_ON", "NEGOTIATION_MESSAGE", "DEAL_AGENT_INVITED"],
  },
  { label: "Scouting", types: ["PLAYER_AVAILABLE"] },
  { label: "Representation", types: ["REPRESENTATION_STARTED", "REPRESENTATION_REVOKED", "REPRESENTATION_EXPIRED"] },
  { label: "Client intelligence", types: ["CLIENT_ALERT"] },
  { label: "Verification", types: ["VERIFICATION_APPROVED", "VERIFICATION_REJECTED"] },
  { label: "Team & approvals", types: ["STAFF_INVITATION", "APPROVAL_REQUESTED", "APPROVAL_DECIDED"] },
  { label: "Loans", types: ["LOAN_STARTED", "LOAN_ENDING_SOON", "LOAN_ENDED", "LOAN_RECALLED", "LOAN_CONVERTED"] },
];

type Channel = "enabled" | "email_enabled" | "push_enabled";

const FYI_PUSH_TITLE = "Not pushed: these stay in the app";

export default function NotificationTypesTable() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery<NotificationPreferencesResponse>({
    queryKey: ["notifications", "preferences"],
    queryFn: () => api.get<NotificationPreferencesResponse>("/notifications/preferences").then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: ({ type, channel, value }: { type: string; channel: Channel; value: boolean }) =>
      api
        .patch<NotificationPreferencesResponse>(`/notifications/preferences/${type}`, { [channel]: value })
        .then((r) => r.data),
    onSuccess: (newData) => queryClient.setQueryData(["notifications", "preferences"], newData),
  });

  if (isLoading) {
    return <div className="flex items-center justify-center py-8"><Spinner size="sm" /></div>;
  }
  if (isError || !data) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
        Failed to load preferences.
      </div>
    );
  }

  const prefMap = Object.fromEntries(data.preferences.map((p) => [p.type, p]));
  const vars = mutation.variables;
  const pending = (type: string, channel: Channel) => mutation.isPending && vars?.type === type && vars?.channel === channel;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end gap-4 px-5 text-[11px] font-semibold uppercase tracking-wider text-text-muted sm:gap-6">
        <span className="flex w-9 justify-center whitespace-nowrap">In-app</span>
        <span className="flex w-9 justify-center whitespace-nowrap">Email</span>
        <span className="flex w-9 justify-center whitespace-nowrap">Push</span>
      </div>

      {TYPE_GROUPS.map((group) => (
        <Card key={group.label} noPadding>
          <div className="border-b border-rule px-5 py-2.5">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">{group.label}</p>
          </div>
          <div className="divide-y divide-rule-faint">
            {group.types.map((type) => {
              const pref = prefMap[type];
              const enabled = pref?.enabled ?? true;
              const emailEnabled = pref?.email_enabled ?? true;
              const pushEnabled = pref?.push_enabled ?? true;
              const fyi = pref?.tier === "FYI";
              const label = TYPE_LABELS[type] ?? type;
              return (
                <div key={type} className="flex items-center justify-between gap-3 px-5 py-3">
                  <span className="min-w-0 text-sm text-text">{label}</span>
                  <div className="flex shrink-0 items-center gap-4 sm:gap-6">
                    <div className="flex w-9 justify-center">
                      <MiniToggle
                        value={enabled}
                        disabled={pending(type, "enabled")}
                        onChange={() => mutation.mutate({ type, channel: "enabled", value: !enabled })}
                        label={`In-app: ${label}`}
                      />
                    </div>
                    <div className="flex w-9 justify-center">
                      <MiniToggle
                        value={emailEnabled}
                        disabled={pending(type, "email_enabled")}
                        onChange={() => mutation.mutate({ type, channel: "email_enabled", value: !emailEnabled })}
                        label={`Email: ${label}`}
                      />
                    </div>
                    <div className="flex w-9 justify-center">
                      <MiniToggle
                        value={fyi ? false : pushEnabled && enabled}
                        disabled={fyi || !enabled || pending(type, "push_enabled")}
                        onChange={() => mutation.mutate({ type, channel: "push_enabled", value: !pushEnabled })}
                        label={`Push: ${label}`}
                        title={fyi ? FYI_PUSH_TITLE : !enabled ? "Turn on in-app first: a push needs the notification" : undefined}
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
        <p className="text-sm text-danger-text">{getApiError(mutation.error, "Failed to save preference.")}</p>
      )}
    </div>
  );
}
