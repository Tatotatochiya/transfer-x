import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Offer, OrderBook, SuggestedTerms } from "../../types/api";
import Spinner from "../../components/ui/Spinner";
import Tabs from "../../components/ui/Tabs";
import SegmentedControl from "../../components/ui/SegmentedControl";
import OfferThread, { offerTimeline } from "../../components/offers/OfferThread";
import ConversationPanel, { useConversationUnread } from "../../components/conversation/ConversationPanel";
import SellerOrderBook from "../../components/sales/SellerOrderBook";
import BuyerOrderBook from "../../components/sales/BuyerOrderBook";
import DemoOfferControls from "../../components/demo/DemoOfferControls";
import OfferHeader from "../../components/offers/OfferHeader";
import OfferMoreMenu from "../../components/offers/OfferMoreMenu";
import OfferStatusCard, { focusOfferHeadline } from "../../components/offers/OfferStatusCard";
import OfferStanding, { RoundsList } from "../../components/offers/OfferStanding";
import OfferTermsCard, { OfferAdvice } from "../../components/offers/OfferTermsCard";
import CounterForm from "../../components/offers/CounterForm";
import RaiseOfferForm from "../../components/offers/RaiseOfferForm";
import { buyerRanking, deadlineText, getOfferStatus, otherName } from "../../components/offers/offerStatus";
import { useConfirm } from "../../context/ConfirmContext";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useLiteOfferCard } from "../../hooks/useLite";
import { useOfferActions } from "../../hooks/useOfferActions";
import { useAIStatus, useOfferAdvice } from "../../hooks/useAssistant";
import { lastChange, offerRounds } from "../../lib/offerChanges";
import { formatDate } from "../../lib/utils";

type Tab = "terms" | "messages" | "bids" | "history";

/**
 * One offer, answer first (offer-room-focus): who and how much, what they
 * just changed, what you can do about it, and how far apart you are — before
 * any scrolling. Below 1024px the sections are tabs and a counter opens in a
 * sheet; from 1024px messages and other bids sit in a rail and a counter
 * opens inside the status card.
 */
export default function OfferDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const confirm = useConfirm();
  const { can } = useClubCapabilities();
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [params, setParams] = useSearchParams();
  const param = params.get("tab");
  const [editing, setEditing] = useState<"counter" | "raise" | null>(() => (params.get("action") === "counter" ? "counter" : null));
  const [prefill, setPrefill] = useState<SuggestedTerms | null>(null);
  const [roundsOpen, setRoundsOpen] = useState(param === "history");
  const [mainTab, setMainTab] = useState<"terms" | "history">(param === "history" ? "history" : "terms");
  const [railTab, setRailTab] = useState<"messages" | "bids">(param === "bids" ? "bids" : "messages");
  const [askedSuggestion, setAskedSuggestion] = useState(false);

  // A push tapped on a phone opens the one-screen decision (the Lite offer
  // card) rather than this full page (mobile notifications §7.3, 4c). Wider
  // screens, and "See full details" from the card, stay here.
  useEffect(() => {
    if (params.get("from") === "push" && id && window.matchMedia?.("(max-width: 639px)").matches) {
      // A push action button ("Ask for £21M", "Accept £18M") carries on to the card.
      const action = params.get("action");
      const amount = params.get("amount");
      const extra = action ? `&action=${encodeURIComponent(action)}${amount ? `&amount=${encodeURIComponent(amount)}` : ""}` : "";
      navigate(`/lite/offers/${id}?from=push${extra}`, { replace: true });
    }
  }, [id, navigate, params]);
  // On a wider screen the push's action is pre-selected here instead: the
  // counter opens with its amount, or Accept is highlighted.
  const pushAction = params.get("from") === "push" ? params.get("action") : null;
  const pushAmount = params.get("amount");

  const { data: offer, isLoading, isError } = useQuery<Offer>({
    queryKey: ["offers", id],
    queryFn: () => api.get<Offer>(`/offers/${id}`).then((r) => r.data),
    enabled: !!id,
  });
  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const myClubId = myClub?.id;
  const isBuyer = !!offer && myClubId === offer.from_club_id;
  const isSeller = !!offer && myClubId === offer.to_club_id;
  const isParty = isBuyer || isSeller;

  const { data: card } = useLiteOfferCard(id, isParty);
  const unread = useConversationUnread({ offerId: id }, isParty);
  const actions = useOfferActions(offer);
  const { data: aiStatus } = useAIStatus();
  const advice = useOfferAdvice(offer?.id ?? "", offer?.last_action_at ?? "", askedSuggestion && !!offer);
  // The rail's "Other bids · n": read from the order book's own cache entry once it has loaded.
  const bookKey = offer?.sale_id ? ["sales", offer.sale_id, "order-book"] : ["offers", "competition", offer?.player_id];
  const { data: book } = useQuery<OrderBook>({
    queryKey: bookKey,
    queryFn: () => api.get<OrderBook>(offer?.sale_id ? `/sales/${offer.sale_id}/order-book` : `/offers/competition/${offer?.player_id}`).then((r) => r.data),
    // Parties only: the seller's tab counts the bids, the buyer's says where
    // they stand. The order book components share this cache entry.
    enabled: isParty && !!offer?.player_id,
    refetchInterval: 300_000,
  });
  const ranking = isBuyer ? buyerRanking(book) : null;

  // "✦ Suggest a counter" fills the form the way "Use these terms" does.
  useEffect(() => {
    if (askedSuggestion && advice.data?.suggested_terms) {
      setPrefill(advice.data.suggested_terms);
      setAskedSuggestion(false);
    }
  }, [askedSuggestion, advice.data]);

  // One page per transfer: once the offer became a deal, the deal page carries
  // the whole story — this negotiation included ("How this was agreed") — so
  // the two clubs go straight there. `replace`, so Back does not bounce here.
  useEffect(() => {
    if (!offer?.deal || !myClub) return;
    if (myClub.id === offer.from_club_id || myClub.id === offer.to_club_id) {
      navigate(`/deals/${offer.deal.id}`, { replace: true });
    }
  }, [offer, myClub, navigate]);

  if (isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }
  if (isError || !offer) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
        Offer not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  const isActive = offer.status === "SENT" || offer.status === "COUNTERED";
  // Whose turn: the party who did NOT last act can respond.
  // last_actor_club_id is null only for legacy offers — fall back to seller's turn for SENT.
  const isMyTurn: boolean = offer.last_actor_club_id != null
    ? offer.last_actor_club_id !== myClubId
    : offer.status === "SENT" ? isSeller : false;
  const canMarketWrite = can("MARKET_WRITE");
  const canAct = isParty && isActive && isMyTurn && canMarketWrite;
  const canWithdraw = isBuyer && isActive && canMarketWrite; // buyer can always pull out regardless of turn

  const side = isBuyer ? "buyer" : isSeller ? "seller" : null;
  const other = otherName(offer, side, card);
  const view = getOfferStatus(offer, {
    side, isMyTurn: isParty && isActive && isMyTurn, canWrite: canMarketWrite, card, pushAction, myClubId, ranking,
  });
  const deadline = deadlineText(card?.expires_at ?? offer.expires_at, new Date());
  const rounds = offerRounds(offer, myClubId);
  const myLastFee = [...rounds].reverse().find((r) => r.side === "me" && r.fee != null)?.fee ?? null;
  const change = lastChange(offer);

  // ── Sections and the ?tab= param (written with replace) ───────────────────
  function writeTab(t: Tab) {
    setParams((p) => { const n = new URLSearchParams(p); n.set("tab", t); return n; }, { replace: true });
  }
  const section: "terms" | "messages" | "bids" = param === "messages" || param === "bids" ? param : "terms";
  function openMessages() {
    if (isDesktop) setRailTab("messages");
    writeTab("messages");
    if (!isDesktop) requestAnimationFrame(() => document.getElementById("offer-sections")?.scrollIntoView({ block: "start" }));
  }
  function showTerms() {
    if (isDesktop) setMainTab("terms");
    writeTab("terms");
    requestAnimationFrame(() => document.getElementById("offer-terms-heading")?.scrollIntoView({ block: "start", behavior: "smooth" }));
  }
  function showHistory() {
    setMainTab("history");
    writeTab("history");
  }

  function finishEditing(sent: boolean) {
    setEditing(null);
    setPrefill(null);
    if (sent) focusOfferHeadline();
  }
  async function withdraw() {
    if (await confirm({ message: "Withdraw this offer?", confirmLabel: "Withdraw", variant: "danger" })) {
      actions.withdraw.mutate(undefined, { onSuccess: () => focusOfferHeadline() });
    }
  }

  const layout = isDesktop ? "inline" : "sheet";
  const replyBy = deadline ? (deadline.text === "deadline passed" ? deadline.text : `reply by ${deadline.text}`) : undefined;
  const editor = editing === "counter" && canAct && side ? (
    <CounterForm
      key={JSON.stringify(prefill)}
      offer={offer} side={side} other={other} replyBy={replyBy} prefill={prefill}
      startFee={pushAction === "counter" ? pushAmount : null}
      card={card} myLastFee={myLastFee} layout={layout} counter={actions.counter} onDone={finishEditing}
      suggest={aiStatus?.available ? {
        onClick: () => setAskedSuggestion(true),
        loading: advice.isFetching,
        summary: advice.data && !advice.data.suggested_terms ? advice.data.summary : null,
      } : undefined}
      formId="offer-counter"
    />
  ) : editing === "raise" && canWithdraw ? (
    <RaiseOfferForm offer={offer} other={other} layout={layout} improve={actions.improve} onDone={finishEditing} formId="offer-raise" />
  ) : null;

  const moreMenu = <OfferMoreMenu offer={offer} isParty={isParty} canWithdraw={canWithdraw} onWithdraw={withdraw} />;
  const termsHeading = !isParty ? "The offer" : change && change.actorClubId === myClubId ? "Your offer"
    : change ? "Their offer" : isBuyer ? "Your offer" : "Their offer";

  const terms = (
    <div className="space-y-4">
      <OfferTermsCard offer={offer} heading={termsHeading} />
      {isParty && isActive && (
        <OfferAdvice offer={offer} canCounter={canAct} onUseTerms={(t) => { setPrefill(t); setEditing("counter"); }} />
      )}
      <DemoOfferControls offerId={offer.id} />
    </div>
  );
  const messages = (
    // The whole transfer's conversation (product ADR 0008): the enquiry
    // before this offer too, with the offer's own events in between.
    <ConversationPanel context={{ offerId: offer.id }} timeline={offerTimeline(offer)}
      placeholder="Write a message… (e.g. why your latest terms are fair)" />
  );
  const bids = isSeller ? (
    <SellerOrderBook saleId={offer.sale_id ?? undefined} playerId={offer.sale_id ? undefined : offer.player_id}
      isOpen={isActive} selectedId={offer.id} />
  ) : (
    <BuyerOrderBook saleId={offer.sale_id ?? undefined} playerId={offer.sale_id ? undefined : offer.player_id} />
  );
  // The buyer's place is in the tab's own name, so it rarely needs opening.
  // The phone's three tabs are ~115px each, so there it's the place alone
  // ("2nd of 4"); the status card says it in full.
  const bidsLabel = isSeller ? (book?.active_count != null ? `Other bids · ${book.active_count}` : "Other bids")
    : ranking ? `Ranking · ${ranking.short}` : "Ranking";
  const bidsTab = isSeller ? "Other bids" : ranking ? ranking.short : "Ranking";

  return (
    <div>
      <OfferHeader offer={offer} moreMenu={moreMenu} />

      <div className="mt-4">
        <OfferStatusCard
          view={view} offer={offer} actions={actions} desktop={isDesktop}
          editing={isDesktop ? editor : null}
          onCounter={() => { setPrefill(null); setEditing("counter"); }}
          onRaise={() => setEditing("raise")}
          onOpenMessages={openMessages}
          onShowAllChanges={showTerms}
        />
      </div>
      <div className="mt-3">
        <OfferStanding
          offer={offer} myClubId={myClubId} side={side} other={other} card={card} desktop={isDesktop}
          roundsOpen={roundsOpen} onToggleRounds={() => setRoundsOpen((v) => !v)} onShowHistory={showHistory}
        />
      </div>

      {!isParty ? (
        <div className="mt-4 max-w-2xl space-y-4">
          <OfferTermsCard offer={offer} heading="The offer" />
          <div className="rounded-xl bg-surface p-4 ring-1 ring-border">
            <OfferThread offer={offer} myClubId={myClubId} canMessage={false} />
          </div>
        </div>
      ) : isDesktop ? (
        <div className="mt-4 grid grid-cols-[minmax(0,1fr)_340px] items-start gap-5">
          <div className="min-w-0">
            <Tabs
              className="mb-4"
              active={mainTab}
              onChange={(k) => { setMainTab(k as typeof mainTab); writeTab(k as Tab); }}
              tabs={[{ key: "terms", label: "Terms" }, { key: "history", label: "Offer history" }]}
            />
            {mainTab === "history" ? (
              <div className="rounded-xl bg-surface p-5 ring-1 ring-border">
                <RoundsList offer={offer} rounds={rounds} other={other} />
                <p className="mt-3 border-t border-rule pt-3 text-sm text-text-muted">Offer made {formatDate(offer.created_at)}</p>
              </div>
            ) : terms}
          </div>
          <aside aria-label="Messages and other bids" className="sticky top-20 flex max-h-[calc(100vh-104px)] flex-col rounded-xl bg-surface ring-1 ring-border">
            <div className="p-3">
              <SegmentedControl
                idPrefix="offer-rail" ariaLabel="Messages and other bids" size="sm"
                items={[
                  { key: "messages", label: "Messages", badge: unread, badgeLabel: "unread" },
                  { key: "bids", label: bidsLabel },
                ]}
                active={railTab}
                onChange={(k) => { setRailTab(k as typeof railTab); writeTab(k as Tab); }}
              />
            </div>
            <div role="tabpanel" id={`offer-rail-panel-${railTab}`} aria-labelledby={`offer-rail-tab-${railTab}`}
              className="min-h-0 flex-1 overflow-y-auto px-3.5 pb-3.5">
              {railTab === "messages" ? messages : bids}
            </div>
          </aside>
        </div>
      ) : (
        <div id="offer-sections" className="mt-5 scroll-mt-16">
          <div className="mb-4">
            <SegmentedControl
              idPrefix="offer-section" ariaLabel="Offer sections"
              items={[{ key: "terms", label: "Terms" }, { key: "messages", label: "Messages", badge: unread, badgeLabel: "unread" }, { key: "bids", label: bidsTab }]}
              active={section}
              onChange={(k) => writeTab(k as Tab)}
            />
          </div>
          <div role="tabpanel" id={`offer-section-panel-${section}`} aria-labelledby={`offer-section-tab-${section}`}>
            {section === "messages" ? <div className="rounded-xl bg-surface p-4 ring-1 ring-border">{messages}</div>
              : section === "bids" ? <div className="rounded-xl bg-surface ring-1 ring-border">{bids}</div>
              : terms}
          </div>
        </div>
      )}

      {!isDesktop && editor}
    </div>
  );
}
