import type { ActiveDealStub } from "../types/api";
import type { DealStage } from "../types/enums";
import { dealStageLabel } from "./badges";
import { formatDate } from "./utils";

/**
 * What the player page offers, by the player's situation (player-actions §4):
 * at most one primary action (the page's only blue button), one secondary, a
 * sentence when something is blocked, and the More menu's items. Pure: the
 * page passes in the flags it already computes, with their existing meaning;
 * this only decides where and how each action shows, never whether it is
 * allowed. The first matching row wins.
 */

export type ActionKey = "sign-in" | "list" | "view-listing" | "view-deal" | "sign-free-agent" | "make-offer" | "pre-contract" | "ask-club";
export type MoreKey = "ask-club" | "compare" | "ask-transferx" | "view-club" | "release-clause";

export interface SituationAction {
  key: ActionKey;
  label: string;
  /** A link; otherwise the page runs its handler for `key`. */
  to?: string;
}

export interface PlayerSituation {
  /** The §4 row, for tests and debugging. */
  row: number;
  primary?: SituationAction;
  secondary?: SituationAction;
  note?: { text: string; tone: "neutral" | "info" };
  more: MoreKey[];
  /** "Ask his club", or "Ask {parent club}" for a player on loan. */
  askLabel: string;
  /** Today's "Transfer in progress" banner, for a deal the viewer isn't on. */
  dealBanner: boolean;
}

export interface SituationInput {
  playerId: string;
  isAuthenticated: boolean;
  isAgent: boolean;
  isPlayerAccount: boolean;
  isMyPlayer: boolean;
  canList: boolean;
  listingsKnown: boolean;
  listingId?: string;
  isOffPlatform: boolean;
  isFreeAgentPlayer: boolean;
  inPreContractWindow: boolean;
  canMarketWrite: boolean;
  activeDeal: ActiveDealStub | null | undefined;
  myClubId?: string;
  contractEndDate: string | null;
  /** His club or world team, for "View {club}" and the off-platform sentence. */
  clubName: string | null;
  /** The club that owns him while he's on loan. */
  parentClubName: string | null;
  /** On loan to the viewer's club (in our squad, not ours to sell). */
  onLoanToUs: boolean;
  hasReleaseClause: boolean;
}

export function playerSituation(i: SituationInput): PlayerSituation {
  const askLabel = i.parentClubName ? `Ask ${i.parentClubName}` : "Ask his club";
  const ask: SituationAction = { key: "ask-club", label: askLabel };
  const makeOffer: SituationAction = { key: "make-offer", label: "Make an offer", to: `/offers/new?player_id=${i.playerId}` };
  const askTransferX = i.isAuthenticated && !i.isAgent && !i.isPlayerAccount;
  // Compare and "✦ Ask TransferX", then "View {club}" where there is one.
  const base = (withClub: boolean): MoreKey[] => [
    "compare",
    ...(askTransferX ? (["ask-transferx"] as MoreKey[]) : []),
    ...(withClub && i.clubName ? (["view-club"] as MoreKey[]) : []),
  ];
  const out = (row: number, s: Partial<PlayerSituation>): PlayerSituation =>
    ({ row, more: [], askLabel, dealBanner: false, ...s });

  // 1. Signed out (a player at a club off TransferX gets row 8's sentence).
  if (!i.isAuthenticated && !i.isOffPlatform) {
    return out(1, { primary: { key: "sign-in", label: "Sign in to make an offer", to: "/login" } });
  }
  // 2. Agents and players: nothing to do here but look.
  if (i.isAgent || i.isPlayerAccount) return out(2, { more: i.clubName ? ["view-club"] : [] });

  // 6–7. A deal in progress pauses everything else. Checked before the
  // own-player rows, so a listing isn't offered while one runs (as today).
  const deal = i.activeDeal?.status === "IN_PROGRESS" ? i.activeDeal : null;
  if (deal) {
    const buyer = deal.buyer_club?.id;
    const seller = deal.seller_club?.id;
    const party = !!i.myClubId && (i.myClubId === buyer || i.myClubId === seller);
    if (party) {
      const other = (i.myClubId === buyer ? deal.seller_club?.name : deal.buyer_club?.name) ?? "the other club";
      const stage = deal.stage ? dealStageLabel(deal.stage as DealStage).toLowerCase() : null;
      return out(6, {
        primary: { key: "view-deal", label: "View the deal", to: `/deals/${deal.id}` },
        note: {
          tone: "info",
          text: `Your deal with ${other} is${stage ? ` at ${stage}` : " in progress"}. New offers are paused until it finishes or falls through.`,
        },
        more: base(!i.isMyPlayer),
      });
    }
    // Not on the deal: today's banner says it, with no link to a deal they can't open.
    return out(7, { dealBanner: true, more: base(!i.isMyPlayer) });
  }

  // 3–5. His own club.
  if (i.isMyPlayer) {
    if (i.canList && i.listingsKnown && !i.listingId) return out(3, { primary: { key: "list", label: "List for sale" }, more: base(false) });
    if (i.canList && i.listingsKnown && i.listingId) {
      return out(4, { primary: { key: "view-listing", label: "View listing", to: `/sales/${i.listingId}` }, more: base(false) });
    }
    const note = i.onLoanToUs && i.parentClubName
      ? { tone: "neutral" as const, text: `He's on loan to you from ${i.parentClubName}. Only ${i.parentClubName} can sell him.` }
      : undefined;
    return out(5, { note, more: base(false) });
  }

  // 8. At a club outside TransferX: an offer could never be answered.
  if (i.isOffPlatform) {
    return out(8, {
      note: {
        tone: "neutral",
        text: `${i.clubName ?? "His club"} is not on TransferX, so an offer could not be answered. Shortlist him to follow his form and contract.`,
      },
      more: base(true),
    });
  }
  // 9. A role that can't trade sees why, not a disabled button.
  if (!i.canMarketWrite) {
    return out(9, { note: { tone: "neutral", text: "Your role can't send offers. Ask your club's owner or sporting director." }, more: base(true) });
  }
  // 10. A free agent: sign him directly.
  if (i.isFreeAgentPlayer) {
    return out(10, {
      primary: { key: "sign-free-agent", label: "Sign him" },
      note: { tone: "neutral", text: "Free agent. There's no fee: you agree his wage and contract." },
      more: base(true),
    });
  }
  const clause: MoreKey[] = i.hasReleaseClause ? ["release-clause"] : [];
  // 11. Contract ending within six months: buy now, or agree a free move.
  if (i.inPreContractWindow) {
    return out(11, {
      primary: makeOffer,
      secondary: { key: "pre-contract", label: "Offer a pre-contract" },
      note: i.contractEndDate
        ? { tone: "neutral", text: `His contract ends ${formatDate(i.contractEndDate)}. You can agree a free move for then, or buy him now.` }
        : undefined,
      more: ["ask-club", ...base(true), ...clause],
    });
  }
  // 12. Everything else: make an offer, or ask first.
  return out(12, { primary: makeOffer, secondary: ask, more: [...base(true), ...clause] });
}
