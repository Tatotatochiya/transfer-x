import { useState, type ReactNode } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AgentNegotiation, Club, Deal, FairValueSignal } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useDealActions } from "../../hooks/useDealActions";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import DealStaffTools from "../../components/admin/DealStaffTools";
import DemoDealControls from "../../components/demo/DemoDealControls";
import AgentNegotiationWorkspace from "../../components/deals/AgentNegotiationWorkspace";
import AgreedOfferHistory from "../../components/deals/AgreedOfferHistory";
import CollapseDealDialog from "../../components/deals/CollapseDealDialog";
import DealHeader from "../../components/deals/DealHeader";
import DealMoreMenu from "../../components/deals/DealMoreMenu";
import DealNotes from "../../components/deals/DealNotes";
import DealProgress from "../../components/deals/DealProgress";
import { useDealRealWorld } from "../../components/deals/DealRealWorldNotice";
import { DealDocuments, DealMessages } from "../../components/deals/DealRoomPanel";
import { useConversationUnread } from "../../components/conversation/ConversationPanel";
import DealStatusCard from "../../components/deals/DealStatusCard";
import DealTermsCard from "../../components/deals/DealTermsCard";
import DealTimeline from "../../components/deals/DealTimeline";
import MedicalResultDialog from "../../components/deals/MedicalResultDialog";
import TermsDiffSpine from "../../components/deals/TermsDiffSpine";
import { getDealStatus } from "../../components/deals/dealStatus";
import SegmentedControl from "../../components/ui/SegmentedControl";
import Spinner from "../../components/ui/Spinner";
import Tabs from "../../components/ui/Tabs";
import { formatDate } from "../../lib/utils";
import MoveReminder from "../../components/transfer/MoveReminder";

type Tab = "overview" | "messages" | "documents" | "history" | "activity";
const TABS: Tab[] = ["overview", "messages", "documents", "history", "activity"];

function focusHeadline() {
  requestAnimationFrame(() => document.getElementById("deal-status-headline")?.focus());
}

/** A row in the phone and tablet Overview that opens in place; its content
 *  (and its queries) render only once it is open. */
function DisclosureRow({ id, title, sub, open, onToggle, children }: {
  id: string; title: string; sub: string; open: boolean; onToggle: () => void; children: ReactNode;
}) {
  return (
    <div className="border-t border-rule first:border-t-0">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={onToggle}
        className="flex min-h-16 w-full items-center justify-between gap-3 px-4 text-left"
      >
        <span>
          <span className="block text-body font-semibold text-text">{title}</span>
          <span className="block text-small text-text-muted">{sub}</span>
        </span>
        <span aria-hidden className="text-text-muted">{open ? "⌃" : "⌄"}</span>
      </button>
      {open && <div id={id} className="px-4 pb-4">{children}</div>}
    </div>
  );
}

/**
 * The deal room, answer first (docs/feature_spec/deal-room-focus): who the
 * deal is for, what to do next and how far along it is, before anything
 * else. Header → status card → progress → sections (tabs below 1024px, a
 * main column and a messages rail from 1024px).
 */
export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { can } = useClubCapabilities();
  const { accessToken, user } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const isAgent = user?.user_type === "AGENT";
  const isPlayer = user?.user_type === "PLAYER";
  const isStaff = user?.is_superuser ?? false;
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [params, setParams] = useSearchParams();
  const param = (TABS as string[]).includes(params.get("tab") ?? "") ? (params.get("tab") as Tab) : "overview";
  const [railTab, setRailTab] = useState<"messages" | "documents">(param === "documents" ? "documents" : "messages");
  const [mainTab, setMainTab] = useState<"overview" | "history" | "activity">(param === "history" || param === "activity" ? param : "overview");
  const [disclosures, setDisclosures] = useState<Set<string>>(() => new Set(param === "history" || param === "activity" ? [param] : []));
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [medicalOpen, setMedicalOpen] = useState(false);
  const [collapseOpen, setCollapseOpen] = useState(false);
  const actions = useDealActions(id, { onDone: focusHeadline });

  const { data: deal, isLoading, isError } = useQuery<Deal>({
    queryKey: ["deals", id],
    queryFn: () => api.get<Deal>(`/deals/${id}`).then((r) => r.data),
    enabled: !!id,
  });
  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });
  // TRA-92: fair value vs the agreed fee, for club/agent/staff identities only —
  // a player identity must never fire the call (the server 403s it anyway, D6)
  const { data: fairValue = null } = useQuery<FairValueSignal | null>({
    queryKey: ["valuation", deal?.player_id, { reference: deal?.agreed_fee }],
    queryFn: () =>
      api.get<FairValueSignal>(`/valuation/players/${deal!.player_id}`, {
        params: deal!.agreed_fee != null ? { reference_price: deal!.agreed_fee } : {},
      }).then((r) => r.data).catch(() => null),
    enabled: !!deal?.player_id && isAuthenticated && !isPlayer,
    staleTime: 300_000,
  });
  // The commission negotiation, while the deal is at that stage (TRA-128/129).
  const { data: negotiation } = useQuery<AgentNegotiation>({
    queryKey: ["deals", id, "agent-negotiation"],
    queryFn: () => api.get<AgentNegotiation>(`/deals/${id}/agent-negotiation`).then((r) => r.data),
    enabled: !!id && !!deal && deal.stage === "AGENT_NEGOTIATION",
    retry: false,
  });
  const isActive = deal?.status === "IN_PROGRESS" || deal?.status === "PENDING_COMPLETION";
  const { data: realWorld } = useDealRealWorld(id, !!isActive);

  // Unread messages for the Messages tab: a club on the deal only (the
  // conversation is the two clubs'; agents and players read the room).
  const onDeal = !!deal && !!myClub && (myClub.id === deal.buyer_club_id || myClub.id === deal.seller_club_id);
  const unread = useConversationUnread({ dealId: id }, onDeal);

  if (isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }
  if (isError || !deal) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-small text-danger-text ring-1 ring-danger-border">
        Deal not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  // ── Who may do what (unchanged, TRA-151 and ADRs 0001/0006) ──────────────
  const isBuyer = myClub?.id === deal.buyer_club_id;
  const isSeller = myClub?.id === deal.seller_club_id;
  const isParty = isBuyer || isSeller;
  const atPersonalTerms = deal.stage === "PERSONAL_TERMS";
  const atPaperwork = deal.stage === "PAPERWORK";
  const canDealWrite = can("DEAL_WRITE");
  const terms = deal.personal_terms;
  const clubCanCollapse = isParty && isActive && canDealWrite;
  // Set personal terms (ADR 0001): the mandated agent if this deal went through
  // AGENT_NEGOTIATION, otherwise the buying club when there's no mandate at all.
  const canSetPersonalTerms = !!isActive && atPersonalTerms && !terms && (
    (isAgent && deal.commission_agent_id != null) ||
    (isBuyer && !isAgent && !isPlayer && deal.commission_agent_id == null && canDealWrite)
  );
  const canRecordConsent = isBuyer && !isAgent && !isPlayer && canDealWrite && !!isActive && atPersonalTerms &&
    terms?.player_consent === "PENDING" && !terms.player_has_account && terms.agent_id == null;
  const canRecordMedical = isStaff || (isBuyer && atPaperwork && deal.status === "IN_PROGRESS" && canDealWrite);
  const viewerSide: "buyer" | "seller" | null = isBuyer ? "buyer" : isSeller ? "seller" : null;
  const canSeeRoom = isParty || isAgent || isPlayer;

  const view = getDealStatus(deal, {
    side: isAgent ? null : viewerSide, isAgent, isPlayer, isStaff, canWrite: canDealWrite,
    canSetPersonalTerms, canRecordConsent, canRecordMedical, negotiation, realWorld,
  });

  // ── Sections and the ?tab= param (written with replace) ───────────────────
  function writeTab(t: Tab) {
    setParams((p) => { const n = new URLSearchParams(p); n.set("tab", t); return n; }, { replace: true });
  }
  const section: Tab = param === "messages" || param === "documents" ? param : "overview";
  function toggleDisclosure(key: string) {
    setDisclosures((s) => { const n = new Set(s); if (n.has(key)) n.delete(key); else n.add(key); return n; });
  }
  function openMessages() {
    if (isDesktop) { setRailTab("messages"); writeTab("messages"); return; }
    writeTab("messages");
    requestAnimationFrame(() => document.getElementById("deal-sections")?.scrollIntoView({ block: "start" }));
  }
  function showSchedule() {
    if (isDesktop) setMainTab("overview");
    writeTab("overview");
    setScheduleOpen(true);
    requestAnimationFrame(() => document.getElementById("deal-terms-heading")?.scrollIntoView({ block: "start", behavior: "smooth" }));
  }

  const roomProps = {
    dealId: deal.id,
    canWrite: !isParty || canDealWrite,
    viewerSide,
  };
  const messages = (
    <DealMessages
      {...roomProps}
      negotiationId={deal.stage === "AGENT_NEGOTIATION" && negotiation ? negotiation.id : null}
      myClubName={isBuyer ? deal.buyer_club?.name : isSeller ? deal.seller_club?.name ?? undefined : undefined}
      theirClubName={isBuyer ? deal.seller_club?.name ?? undefined : isSeller ? deal.buyer_club?.name : undefined}
    />
  );
  const documents = <DealDocuments {...roomProps} />;
  const history = deal.offer_id && isParty ? <AgreedOfferHistory offerId={deal.offer_id} myClubId={myClub?.id} /> : null;
  const notes = <DealNotes deal={deal} canAdd={isParty && !!isActive && canDealWrite} />;

  const overview = (
    <div className="space-y-4">
      {isAgent && deal.stage === "AGENT_NEGOTIATION" && deal.status === "IN_PROGRESS" && (
        <AgentNegotiationWorkspace dealId={deal.id} negotiation={negotiation ?? null} />
      )}
      <TermsDiffSpine dealId={deal.id} isBuyer={isBuyer} />
      <DealTermsCard
        deal={deal} isPlayer={isPlayer} isBuyer={isBuyer} fairValue={fairValue}
        canRecordMedical={canRecordMedical} onRecordMedical={() => setMedicalOpen(true)}
        scheduleOpen={scheduleOpen} onToggleSchedule={() => setScheduleOpen((v) => !v)}
      />
      {isStaff && <DealStaffTools deal={deal} />}
      {!isDesktop && (
        <div className="rounded-xl bg-surface ring-1 ring-border">
          {history && (
            <DisclosureRow id="deal-history" title="How this was agreed" sub="The offer and its negotiation"
              open={disclosures.has("history")} onToggle={() => toggleDisclosure("history")}>
              {history}
            </DisclosureRow>
          )}
          <DisclosureRow id="deal-notes" title="Notes"
            sub={deal.deal_notes.length ? `${deal.deal_notes.length} note${deal.deal_notes.length === 1 ? "" : "s"}` : "No notes yet"}
            open={disclosures.has("notes")} onToggle={() => toggleDisclosure("notes")}>
            {notes}
          </DisclosureRow>
          <DisclosureRow id="deal-activity" title="Activity" sub={`Everything that happened on this deal since ${formatDate(deal.created_at)}`}
            open={disclosures.has("activity")} onToggle={() => toggleDisclosure("activity")}>
            <DealTimeline dealId={deal.id} />
          </DisclosureRow>
        </div>
      )}
    </div>
  );

  const moreMenu = (
    <DealMoreMenu
      dealId={deal.id}
      playerName={deal.player?.name ?? ""}
      canAsk={isParty}
      canCollapse={!!clubCanCollapse}
      onCollapse={() => setCollapseOpen(true)}
    />
  );

  return (
    <div>
      <DealHeader deal={deal} moreMenu={moreMenu} />

      <div className="mt-4">
        <DealStatusCard
          view={view} deal={deal} viewerSide={isAgent ? null : viewerSide} actions={actions}
          onOpenMessages={openMessages} onShowSchedule={showSchedule} onRecordMedical={() => setMedicalOpen(true)}
          reminder={view.tone === "wait" && (isParty || isAgent) ? <MoveReminder subjectType="deal" subjectId={deal.id} /> : undefined}
        />
        <DemoDealControls dealId={deal.id} waiting={view.tone === "wait" && isParty} waitingOn={view.overline} />
      </div>
      <div className="mt-3">
        <DealProgress deal={deal} negotiation={negotiation} />
      </div>

      {isDesktop ? (
        <div className={`mt-4 ${canSeeRoom ? "grid grid-cols-[minmax(0,1fr)_340px] items-start gap-5" : ""}`}>
          <div className="min-w-0">
            <Tabs
              className="mb-4"
              active={mainTab}
              onChange={(k) => { setMainTab(k as typeof mainTab); writeTab(k as Tab); }}
              tabs={[
                { key: "overview", label: "Overview" },
                ...(history ? [{ key: "history", label: "How this was agreed" }] : []),
                { key: "activity", label: "Activity" },
              ]}
            />
            {mainTab === "history" && history ? (
              <div className="rounded-xl bg-surface p-5 ring-1 ring-border">{history}</div>
            ) : mainTab === "activity" ? (
              <div className="space-y-6 rounded-xl bg-surface p-5 ring-1 ring-border">
                <section>
                  <h3 className="mb-2 text-body font-bold text-text">Notes</h3>
                  {notes}
                </section>
                <section>
                  <h3 className="mb-3 text-body font-bold text-text">Activity</h3>
                  <DealTimeline dealId={deal.id} />
                </section>
              </div>
            ) : overview}
          </div>
          {canSeeRoom && (
            <aside aria-label="Messages and documents" className="sticky top-20 flex max-h-[calc(100vh-104px)] flex-col rounded-xl bg-surface ring-1 ring-border">
              <div className="p-3">
                <SegmentedControl
                  idPrefix="deal-rail" ariaLabel="Messages and documents" size="sm"
                  items={[{ key: "messages", label: "Messages", badge: unread, badgeLabel: "unread" }, { key: "documents", label: "Documents" }]}
                  active={railTab}
                  onChange={(k) => { setRailTab(k as typeof railTab); writeTab(k as Tab); }}
                />
              </div>
              <div role="tabpanel" id={`deal-rail-panel-${railTab}`} aria-labelledby={`deal-rail-tab-${railTab}`}
                className="min-h-0 flex-1 overflow-y-auto px-3.5 pb-3.5">
                {railTab === "messages" ? messages : documents}
              </div>
            </aside>
          )}
        </div>
      ) : (
        <div id="deal-sections" className="mt-5 scroll-mt-16">
          {canSeeRoom && (
            <div className="mb-4">
              <SegmentedControl
                idPrefix="deal-section" ariaLabel="Deal sections"
                items={[{ key: "overview", label: "Overview" }, { key: "messages", label: "Messages", badge: unread, badgeLabel: "unread" }, { key: "documents", label: "Documents" }]}
                active={section}
                onChange={(k) => writeTab(k as Tab)}
              />
            </div>
          )}
          <div role={canSeeRoom ? "tabpanel" : undefined} id={`deal-section-panel-${section}`}
            aria-labelledby={canSeeRoom ? `deal-section-tab-${section}` : undefined}>
            {section === "messages" && canSeeRoom ? <div className="rounded-xl bg-surface p-4 ring-1 ring-border">{messages}</div>
              : section === "documents" && canSeeRoom ? <div className="rounded-xl bg-surface p-4 ring-1 ring-border">{documents}</div>
              : overview}
          </div>
        </div>
      )}

      <MedicalResultDialog open={medicalOpen} onClose={() => setMedicalOpen(false)} medicalCheck={deal.medical_check} actions={actions} />
      <CollapseDealDialog open={collapseOpen} onClose={() => setCollapseOpen(false)} actions={actions} />
    </div>
  );
}
