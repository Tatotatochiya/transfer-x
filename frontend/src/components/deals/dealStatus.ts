/**
 * What the deal room says first (docs/feature_spec/deal-room-focus §5.2):
 * who must do what next, worked out from the deal alone. Pure, so every
 * stage and viewer is testable; permissions are computed by the page and
 * passed in, never re-derived here.
 */
import type { AgentNegotiation, Deal } from "../../types/api";
import type { DealStage } from "../../types/enums";
import { dealStageLabel } from "../../lib/badges";
import { formatCurrency, formatDate, formatWage } from "../../lib/utils";

export type StatusTone = "you" | "wait" | "info" | "hold" | "done" | "collapsed";

export type StatusAction =
  | { kind: "advance"; label: string }
  | { kind: "complete"; label: "Complete transfer" }
  | { kind: "paperwork"; step: "sign-agreement" | "submit-registration"; label: string }
  | { kind: "record-medical"; label: string }
  | { kind: "commission-respond"; agreement: "AGREED" | "DECLINED"; label: string; danger?: boolean }
  | { kind: "propose-terms"; label: string }
  | { kind: "record-consent"; label: string }
  | { kind: "player-consent"; agreement: "AGREED" | "DECLINED"; label: string; danger?: boolean }
  | { kind: "open-messages"; label: string }
  | { kind: "open-profile"; label: string }
  | { kind: "show-schedule"; label: string };

export interface StatusStrip { title: string; body: string }

export interface DealStatusView {
  tone: StatusTone;
  overline: string;
  meta?: string;
  headline: string;
  body?: string;
  primary?: StatusAction;
  secondary?: StatusAction;
  showChecklist: boolean;
  strips: StatusStrip[];
}

export interface RealWorld { hold: string | null; window: string | null; note?: string | null }

export interface StatusViewer {
  side: "buyer" | "seller" | null;
  isAgent: boolean;
  isPlayer: boolean;
  isStaff: boolean;
  canWrite: boolean;
  canSetPersonalTerms: boolean;
  canRecordConsent: boolean;
  canRecordMedical: boolean;
  negotiation: AgentNegotiation | null | undefined;
  realWorld: RealWorld | undefined;
  now?: Date;
}

// ── Names ─────────────────────────────────────────────────────────────────────

const DAY = 86_400_000;

function names(deal: Deal, viewer: StatusViewer) {
  const P = deal.player?.name ?? "the player";
  const B = deal.buyer_club?.name ?? "the buying club";
  const S = deal.seller_club_id ? deal.seller_club?.name ?? "the selling club" : null;
  const other = viewer.side === "buyer" ? S : viewer.side === "seller" ? B : null;
  const A = deal.agent?.display_name ?? "the agent";
  return { P, B, S, other, A };
}

const isOpen = (deal: Deal) => deal.status === "IN_PROGRESS" || deal.status === "PENDING_COMPLETION";
const isLoan = (deal: Deal) => deal.deal_type === "LOAN";
const hasFee = (deal: Deal) => deal.agreed_fee != null && Number(deal.agreed_fee) > 0;

/** "6.0% (£300,000)": whichever exist. Never an amount worked out from the pct. */
export function commissionText(pct: number | null | undefined, amount: number | null | undefined): string {
  const parts: string[] = [];
  if (pct != null) parts.push(`${(Number(pct) * 100).toFixed(1)}%`);
  if (amount != null) parts.push(pct != null ? `(${formatCurrency(Number(amount))})` : formatCurrency(Number(amount)));
  return parts.join(" ") || "a commission";
}

const PAYER: Record<string, string> = { BUYER: "the buying club", SELLER: "the selling club", PLAYER: "the player" };

function termsSentence(wage: number | null | undefined, years: number | null | undefined): string {
  const w = wage != null ? formatWage(Number(wage)) : null;
  const y = years != null ? `${years} year${years === 1 ? "" : "s"}` : null;
  return [w, y].filter(Boolean).join(" for ");
}

/** The real-world and window notices, as strips (rule R-e). */
export function realWorldStrips(rw: RealWorld | undefined): StatusStrip[] {
  if (!rw) return [];
  const out: StatusStrip[] = [];
  if (rw.hold) out.push({
    title: "Completion on hold: moved in real life",
    body: `${rw.hold} Talks and paperwork carry on as normal. Only completing the transfer waits.`,
  });
  if (rw.window) out.push({
    title: "Completes when the transfer window opens",
    body: `${rw.window} Talks and paperwork carry on as normal. Both clubs are told when it opens.`,
  });
  if (!rw.hold && rw.note) out.push({ title: "Moved in real life", body: rw.note });
  return out;
}

/** The consent-pending body, as the personal-terms banner put it. */
function pendingTermsBody(deal: Deal, isBuyer: boolean): string {
  const terms = deal.personal_terms!;
  const agentName = deal.agent ? `${deal.agent.display_name} (${deal.agent.agency_name})` : null;
  const buyerName = deal.buyer_club?.name ?? "The buying club";
  if (terms.agent_id) {
    return terms.player_has_account
      ? `The terms have been sent to the player. He or his agent${agentName ? `, ${agentName},` : ""} can accept them.`
      : `The player has no TransferX account, so his agent${agentName ? `, ${agentName},` : ""} responds on his behalf.`;
  }
  if (terms.player_has_account) return "The terms have been sent to the player. The deal moves on once he accepts them.";
  return isBuyer
    ? "The player has no TransferX account or agent. Record his answer once you have it in writing."
    : `The player has no TransferX account or agent, so ${buyerName} records his answer.`;
}

// ── The table ─────────────────────────────────────────────────────────────────

type Row = Omit<DealStatusView, "showChecklist" | "strips"> & { showChecklist?: boolean; strips?: StatusStrip[] };

function row(deal: Deal, v: StatusViewer): Row {
  const { P, B, S, other, A } = names(deal, v);
  const party = v.side != null && !v.isAgent;
  const msgOther: StatusAction = { kind: "open-messages", label: other ? `Message ${other}` : "Open messages" };
  const fee = formatCurrency(Number(deal.agreed_fee ?? 0));
  const rw = v.realWorld;

  // 1–2: finished deals.
  if (deal.status === "COLLAPSED") {
    const by = deal.collapsed_by_club_id;
    const who = !by ? null
      : by === deal.buyer_club_id ? (v.side === "buyer" ? "You" : B)
      : by === deal.seller_club_id ? (v.side === "seller" ? "You" : S)
      : null;
    const reason = deal.collapse_reason ? `“${deal.collapse_reason}”` : null;
    const body = who && reason ? `${who} called it off: ${reason}`
      : who ? `${who} called it off.`
      : reason ? `Reason: ${reason}`
      : undefined;
    return { tone: "collapsed", overline: "Collapsed", meta: formatDate(deal.updated_at), headline: "This transfer fell through", body };
  }
  if (deal.status === "COMPLETED") {
    const headline = isLoan(deal)
      ? v.side === "buyer"
        ? `${P} is on loan at ${B}${deal.loan_end ? ` until ${formatDate(deal.loan_end)}` : ""}`
        : `${P} joined ${B} on loan`
      : v.side === "buyer" ? `${P} is a ${B} player` : `${P} joined ${B}`;
    let body: string | undefined;
    if (deal.instalments.length > 0) {
      const next = [...deal.instalments].filter((i) => !i.paid).sort((a, b) => a.due_date.localeCompare(b.due_date))[0];
      body = next ? `Next instalment: ${formatCurrency(Number(next.amount))} due ${formatDate(next.due_date)}.` : "All instalments are paid.";
    } else if (hasFee(deal)) {
      body = "Paid on completion.";
    }
    return {
      tone: "done", overline: "Completed", meta: deal.completed_at ? formatDate(deal.completed_at) : undefined, headline, body,
      secondary: deal.instalments.length > 0 ? { kind: "show-schedule", label: "View the payment schedule" } : undefined,
    };
  }

  // 3–5: confirmed, only completion left.
  if (deal.stage === "CONFIRMED") {
    const strips = realWorldStrips(rw);
    const held = rw?.hold ? strips[0] : rw?.window ? strips.find((s) => s.title.startsWith("Completes")) : undefined;
    if (held) {
      return {
        tone: "hold", overline: "Completion on hold",
        headline: rw?.hold ? `Completion waits: ${P} has moved in real life` : "Completes when the transfer window opens",
        body: held.body, strips: strips.filter((s) => s !== held),
      };
    }
    if (party) {
      return {
        tone: "you", overline: "Your move", headline: "Complete the transfer",
        body: `Both clubs finished the paperwork. Completing registers ${P} at ${B}. It can't be undone.`,
        primary: { kind: "complete", label: "Complete transfer" },
      };
    }
    return { tone: "info", overline: "Ready to complete", headline: "The clubs can now complete the transfer" };
  }

  // 6–8: paperwork.
  if (deal.stage === "PAPERWORK") {
    const steps = deal.paperwork ?? [];
    const done = steps.filter((s) => s.done).length;
    const progress = `${done} of ${steps.length} paperwork steps done.`;
    const mine = party ? steps.find((s) => !s.done && s.owner === v.side) : undefined;
    if (mine) {
      const otherSigned = v.side === "buyer" ? deal.agreement_signed_by_seller_at : deal.agreement_signed_by_buyer_at;
      const body = progress
        + (otherSigned && other ? ` ${other} signed the agreement on ${formatDate(otherSigned)}.` : "")
        + " When every step is done the deal is confirmed.";
      const primary: StatusAction = mine.key === "medical"
        ? { kind: "record-medical", label: "Record medical result" }
        : mine.key === "registration"
          ? { kind: "paperwork", step: "submit-registration", label: "Mark registration submitted" }
          : { kind: "paperwork", step: "sign-agreement", label: "Mark the agreement signed" };
      const headline = mine.key === "medical" ? "Record the medical result"
        : mine.key === "registration" ? "Submit the registration" : "Sign the transfer agreement";
      return { tone: "you", overline: "Your move", headline, body, primary, showChecklist: true };
    }
    if (party) {
      const next = steps.find((s) => !s.done);
      return {
        tone: "wait", overline: `Waiting on ${other ?? B}`, headline: next?.label ?? "The paperwork is nearly done",
        body: progress, secondary: msgOther, showChecklist: true,
      };
    }
    return { tone: "info", overline: "Paperwork", headline: "The clubs are completing the paperwork",
      body: `${done} of ${steps.length} steps done.`, showChecklist: true };
  }

  // 9–15: personal terms.
  if (deal.stage === "PERSONAL_TERMS") {
    const terms = deal.personal_terms;
    if (!terms) {
      if (v.canSetPersonalTerms) {
        return { tone: "you", overline: "Your move", headline: `Propose personal terms to ${P}`,
          body: "The deal moves on once he accepts them.", primary: { kind: "propose-terms", label: "Propose terms" } };
      }
      const viaAgent = deal.commission_agent_id != null;
      return {
        tone: "wait", overline: viaAgent ? "Waiting on the agent" : `Waiting on ${B}`,
        headline: `${viaAgent ? A : B} is preparing ${P}'s personal terms`,
        secondary: party ? { kind: "open-messages", label: "Open messages" } : undefined,
      };
    }
    if (terms.player_consent === "AGREED") {
      if (party) {
        const t = termsSentence(terms.wage_weekly, terms.length_years);
        return { tone: "you", overline: "Your move", headline: "Move the deal on to paperwork",
          body: t ? `${P} accepted ${t}.` : `${P} accepted the terms.`,
          primary: { kind: "advance", label: "Move on to paperwork" } };
      }
      return { tone: "wait", overline: "Waiting on the clubs", headline: `${P} accepted the terms. The clubs move the deal on to paperwork.` };
    }
    // PENDING (a declined proposal collapses the deal).
    if (v.canRecordConsent) {
      return { tone: "you", overline: "Your move", headline: `Record ${P}'s answer to the terms`,
        body: "He has no TransferX account or agent. Upload the signed terms to record that he agreed.",
        primary: { kind: "record-consent", label: "He agreed" },
        secondary: { kind: "player-consent", agreement: "DECLINED", label: "He declined", danger: true } };
    }
    if (v.isAgent) {
      return { tone: "you", overline: "Your move", headline: `Answer for ${P}`,
        body: terms.player_has_account ? "He can answer himself, or you can answer for him." : "He has no TransferX account, so you answer for him.",
        primary: { kind: "player-consent", agreement: "AGREED", label: "Accept for player" },
        secondary: { kind: "player-consent", agreement: "DECLINED", label: "Decline for player", danger: true } };
    }
    if (v.isPlayer) {
      const t = termsSentence(terms.wage_weekly, terms.length_years);
      return { tone: "you", overline: "Your move", headline: "Answer the personal terms",
        body: `${t ? `${B} offers ${t}. ` : ""}You answer on your player page.`,
        primary: { kind: "open-profile", label: "Answer the terms" } };
    }
    return {
      tone: "wait", overline: terms.agent_id ? "Waiting on the agent" : `Waiting on ${P}`,
      headline: `${P} hasn't answered the personal terms yet`, body: pendingTermsBody(deal, v.side === "buyer"),
      secondary: party ? { kind: "open-messages", label: "Open messages" } : undefined,
    };
  }

  // 16–23: agent negotiation.
  if (deal.stage === "AGENT_NEGOTIATION") {
    const neg = v.negotiation ?? null;
    const proposed = !!neg && (neg.commission_pct != null || neg.commission_amount != null);
    const commission = commissionText(neg?.commission_pct, neg?.commission_amount);
    if (v.isAgent) {
      if (!proposed) return { tone: "you", overline: "Your move", headline: "Propose your commission",
        body: `Set it in the negotiation workspace below. ${B} then answers it.` };
      if (neg!.club_agreement === "PENDING") return { tone: "wait", overline: `Waiting on ${B}`,
        headline: `${B} is considering your proposal`, body: `You asked for ${commission}.` };
      if (neg!.club_agreement === "DECLINED") return { tone: "you", overline: "Your move",
        headline: `${B} declined your proposal`, body: "Change the terms below to send a new one." };
    }
    if (neg?.club_agreement === "AGREED" && proposed) {
      if (v.isAgent || (party && v.side === "buyer")) {
        return { tone: "you", overline: "Your move", headline: "Move the deal on to personal terms",
          body: `${B} agreed ${commission} with ${A}.`, primary: { kind: "advance", label: "Move on to personal terms" } };
      }
      if (party) {
        return { tone: "wait", overline: `Waiting on ${B}`, headline: `${B} agreed the agent's commission`,
          body: `${B} or ${A} moves the deal on to personal terms next.`, secondary: { kind: "open-messages", label: `Message ${B}` } };
      }
    }
    if (party) {
      if (!proposed) return { tone: "wait", overline: "Waiting on the agent", headline: `${A} hasn't proposed his commission yet`,
        body: `Personal terms start once ${B} agrees the commission.`, secondary: { kind: "open-messages", label: "Open messages" } };
      if (neg!.club_agreement === "PENDING") {
        if (v.side === "buyer") {
          const payer = neg!.commission_payer ? `Paid by ${PAYER[neg!.commission_payer] ?? neg!.commission_payer.toLowerCase()}.` : "";
          return { tone: "you", overline: "Your move", headline: `${A} asks for ${commission}`,
            body: [payer, neg!.additional_conditions ? `Conditions: ${neg!.additional_conditions}` : ""].filter(Boolean).join(" ") || undefined,
            primary: { kind: "commission-respond", agreement: "AGREED", label: "Accept proposal" },
            secondary: { kind: "commission-respond", agreement: "DECLINED", label: "Decline", danger: true } };
        }
        return { tone: "wait", overline: `Waiting on ${B}`, headline: `${B} is answering the agent's commission proposal`,
          secondary: { kind: "open-messages", label: `Message ${B}` } };
      }
      if (neg!.club_agreement === "DECLINED") return { tone: "wait", overline: "Waiting on the agent",
        headline: `${B} declined the commission proposal`, body: `${A} can send a new proposal.`,
        secondary: { kind: "open-messages", label: "Open messages" } };
    }
  }

  // 24: agreement.
  if (deal.stage === "AGREEMENT" && party) {
    const agreed = S == null
      ? `${B} agreed to sign ${P}.`
      : isLoan(deal)
        ? `Both clubs agreed the loan${hasFee(deal) ? ` for ${fee}` : ""}.`
        : hasFee(deal) ? `Both clubs agreed ${fee}.` : "Both clubs agreed the deal.";
    return { tone: "you", overline: "Your move", headline: "Move the deal on to personal terms",
      body: `${agreed} ${S == null ? `${B} moves it on` : "Either club can move it on"}; ${P} then has to agree his personal terms.`,
      primary: { kind: "advance", label: "Move on to personal terms" } };
  }

  // 25: anyone else.
  return { tone: "info", overline: dealStageLabel(deal.stage), headline: `This deal is at ${dealStageLabel(deal.stage).toLowerCase()}` };
}

export function getDealStatus(deal: Deal, viewer: StatusViewer): DealStatusView {
  const r = row(deal, viewer);
  const now = viewer.now ?? new Date();
  const party = viewer.side != null && !viewer.isAgent;
  const view: DealStatusView = { ...r, showChecklist: r.showChecklist ?? false, strips: r.strips ?? [] };
  const { other } = names(deal, viewer);

  // R-a: a club party whose role can't act.
  if (party && !viewer.canWrite && view.tone === "you") {
    view.tone = "info";
    view.overline = "Your club's move";
    view.body = "Your role can see this deal but can't act on it.";
    view.primary = undefined;
    view.secondary = undefined;
  }
  // R-b: idle.
  if (view.tone === "wait") {
    const idle = Math.floor((now.getTime() - new Date(deal.updated_at).getTime()) / DAY);
    if (idle >= 3) view.meta = `${idle} days without movement`;
  }
  // R-c: due (set by the backend on entering Confirmed).
  if (view.tone === "you" && deal.sla_deadline) view.meta = `due ${formatDate(deal.sla_deadline)}`;
  // R-d: a way to talk to the other club.
  if (party && view.tone === "you" && !view.secondary) {
    view.secondary = { kind: "open-messages", label: other ? `Message ${other}` : "Open messages" };
  }
  // R-e: real-world and window notices on open deals before Confirmed.
  if (isOpen(deal) && deal.stage !== "CONFIRMED") view.strips = realWorldStrips(viewer.realWorld);
  return view;
}

// ── Stages ────────────────────────────────────────────────────────────────────

/** Every deal goes through personal terms; agent commission only with an agent (D7). */
export function dealStages(deal: Deal, negotiation: AgentNegotiation | null | undefined): DealStage[] {
  const hasAgent = deal.commission_agent_id != null || negotiation != null
    || deal.stage === "AGENT_NEGOTIATION" || deal.agent != null;
  return [
    "AGREEMENT", ...(hasAgent ? ["AGENT_NEGOTIATION" as DealStage] : []),
    "PERSONAL_TERMS", "PAPERWORK", "CONFIRMED", "COMPLETED",
  ];
}

export const STAGE_SHORT: Record<DealStage, string> = {
  AGREEMENT: "Agreement", AGENT_NEGOTIATION: "Agent", PERSONAL_TERMS: "Personal terms",
  PAPERWORK: "Paperwork", CONFIRMED: "Confirmed", COMPLETED: "Completed",
};
export const STAGE_LONG: Record<DealStage, string> = { ...STAGE_SHORT, AGENT_NEGOTIATION: "Agent commission" };

export type StageState = "done" | "now" | "next";

export function stageState(deal: Deal, stages: DealStage[], stage: DealStage): StageState {
  if (deal.status === "COMPLETED") return "done";
  const i = stages.indexOf(stage);
  const cur = stages.indexOf(deal.stage);
  return i < cur ? "done" : i === cur ? "now" : "next";
}

/** One short line per stage, for the phone list and the summary sentence. */
export function stageNote(deal: Deal, negotiation: AgentNegotiation | null | undefined, stage: DealStage, state: StageState): string | null {
  const P = deal.player?.name ?? "the player";
  const first = deal.player?.name?.split(" ")[0] ?? "The player";
  const B = deal.buyer_club?.name ?? "the buying club";
  const A = deal.agent?.display_name ?? "The agent";
  const terms = deal.personal_terms;
  switch (stage) {
    case "AGREEMENT":
      return state === "done" ? (hasFee(deal) ? `Clubs agreed ${formatCurrency(Number(deal.agreed_fee))}` : "Clubs agreed") : state === "now" ? "Clubs are finalising the deal" : null;
    case "AGENT_NEGOTIATION": {
      if (state === "next") return "Not started";
      if (state === "now") return `${A} and ${B} are agreeing commission`;
      const pct = deal.agent_commission_pct ?? negotiation?.commission_pct;
      return pct != null ? `Agent agreed ${(Number(pct) * 100).toFixed(1)}%` : "Commission agreed";
    }
    case "PERSONAL_TERMS": {
      if (state === "next") return "Not started";
      if (state === "done") {
        const wage = deal.agreed_wage_weekly ?? terms?.wage_weekly;
        return wage != null ? `${first} agreed ${formatWage(Number(wage))}` : `${first} agreed his terms`;
      }
      if (!terms) return "Terms not proposed yet";
      return terms.player_consent === "AGREED" ? `${P} accepted` : `Waiting for ${P}'s answer`;
    }
    case "PAPERWORK": {
      if (state === "next") return "Not started";
      if (state === "done") return "Paperwork done";
      const steps = deal.paperwork ?? [];
      return `Paperwork ${steps.filter((s) => s.done).length} of ${steps.length}`;
    }
    case "CONFIRMED":
      return state === "done" ? "Confirmed" : state === "now" ? "Ready to complete" : "When the paperwork is done";
    case "COMPLETED":
      return state === "done" && deal.completed_at ? formatDate(deal.completed_at) : null;
  }
}
