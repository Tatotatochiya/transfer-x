import { describe, expect, it } from "vitest";
import type { AgentNegotiation, Deal, PaperworkStep, PersonalTerms } from "../../types/api";
import { dealStages, getDealStatus, stageNote, type StatusViewer } from "./dealStatus";

const NOW = new Date("2026-11-10T12:00:00Z");

const steps = (done: Partial<Record<PaperworkStep["key"], boolean>> = {}): PaperworkStep[] => [
  { key: "agreement_buyer", owner: "buyer", label: "Buying club signs the transfer agreement", done: !!done.agreement_buyer },
  { key: "agreement_seller", owner: "seller", label: "Selling club signs the transfer agreement", done: !!done.agreement_seller },
  { key: "medical", owner: "buyer", label: "Buying club records a passed medical", done: !!done.medical },
  { key: "registration", owner: "buyer", label: "Buying club submits the registration", done: !!done.registration },
];

function deal(over: Partial<Deal> = {}): Deal {
  return {
    id: "d1", sale_id: null, bid_id: null, offer_id: "o1", buyer_club_id: "b", seller_club_id: "s", player_id: "p",
    agreed_fee: 5_400_000, agreed_wage_weekly: null, status: "IN_PROGRESS", stage: "AGREEMENT", deal_type: "PERMANENT",
    loan_start: null, loan_end: null, loan_fee: null, option_to_buy: null, obligation_to_buy: false, obligation_conditions: null,
    wage_split_pct: null, signing_bonus: null, contract_length_years: null, agreement_signed_by_buyer_at: null,
    agreement_signed_by_seller_at: null, registration_submitted_at: null, paperwork: steps(), sla_deadline: null,
    recall_allowed: false, sell_on_pct: null, clauses: [], instalments: [], agent_commission_pct: null,
    agent_commission_amount: null, commission_payer: null, commission_agent_id: null, personal_terms: null,
    medical_check: null, notes: null, completed_at: null, created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z", is_auction_deal: false,
    buyer_club: { id: "b", name: "Meridian FC" } as Deal["buyer_club"],
    seller_club: { id: "s", name: "Castlebrook" } as Deal["seller_club"],
    player: { id: "p", name: "Bram Wouters", position: "MID" } as Deal["player"],
    deal_notes: [], agent: null, ...over,
  } as Deal;
}

const terms = (over: Partial<PersonalTerms> = {}): PersonalTerms => ({
  id: "t", deal_id: "d1", agent_id: null, wage_weekly: 38_000, signing_bonus: null, length_years: 4,
  player_consent: "PENDING", proposed_by: "BUYER", player_has_account: false, agreed_at: null, created_at: "2026-11-05T10:00:00Z",
  buyer_club_id: "b", buyer_club_name: "Meridian FC", consent_evidence_attachment_id: null, ...over,
});

const neg = (over: Partial<AgentNegotiation> = {}): AgentNegotiation => ({
  id: "n", deal_id: "d1", agent_id: "a", status: "IN_PROGRESS" as AgentNegotiation["status"], commission_pct: 0.06,
  commission_amount: 324_000, commission_payer: "BUYER", additional_conditions: null, club_agreement: "PENDING", proposed_by: "AGENT",
  created_at: "2026-11-02T10:00:00Z", agreed_at: null, ...over,
});

function viewer(over: Partial<StatusViewer> = {}): StatusViewer {
  return {
    side: "buyer", isAgent: false, isPlayer: false, isStaff: false, canWrite: true, canSetPersonalTerms: false,
    canRecordConsent: false, canRecordMedical: false, negotiation: null, realWorld: undefined, now: NOW, ...over,
  };
}

const agent = { display_name: "Luka Brandt", agency_name: "LB Sports", id: "a" };

describe("getDealStatus: finished deals", () => {
  it("a collapsed deal fell through", () => {
    const v = getDealStatus(deal({ status: "COLLAPSED", stage: "PAPERWORK" }), viewer());
    expect(v).toMatchObject({ tone: "collapsed", overline: "Collapsed", headline: "This transfer fell through" });
    expect(v.primary).toBeUndefined();
  });

  it("a collapsed deal says who called it off, and why when they said", () => {
    const d = deal({ status: "COLLAPSED", collapsed_by_club_id: "s", collapse_reason: "Failed the medical" });
    expect(getDealStatus(d, viewer()).body).toBe("Castlebrook called it off: “Failed the medical”");
    expect(getDealStatus(d, viewer({ side: "seller" })).body).toBe("You called it off: “Failed the medical”");
    expect(getDealStatus(deal({ status: "COLLAPSED", collapsed_by_club_id: "b" }), viewer()).body).toBe("You called it off.");
    expect(getDealStatus(deal({ status: "COLLAPSED", collapse_reason: "Duplicate deal" }), viewer()).body).toBe("Reason: “Duplicate deal”");
    expect(getDealStatus(deal({ status: "COLLAPSED" }), viewer()).body).toBeUndefined();
  });

  it("a completed deal names the next instalment, or says all are paid", () => {
    const inst = (paid: boolean, due: string) => ({ id: due, deal_id: "d1", due_date: due, amount: 1_800_000, paid, paid_at: paid ? due : null });
    const unpaid = getDealStatus(deal({ status: "COMPLETED", stage: "COMPLETED", completed_at: "2026-11-09T10:00:00Z",
      instalments: [inst(true, "2026-11-09"), inst(false, "2027-01-15")] as Deal["instalments"] }), viewer());
    expect(unpaid).toMatchObject({ tone: "done", headline: "Bram Wouters is a Meridian FC player" });
    expect(unpaid.body).toBe("Next instalment: £1.8M due 15 Jan 2027.");
    expect(unpaid.secondary).toMatchObject({ kind: "show-schedule" });
    const paid = getDealStatus(deal({ status: "COMPLETED", stage: "COMPLETED", instalments: [inst(true, "2026-11-09")] as Deal["instalments"] }), viewer({ side: "seller" }));
    expect(paid.body).toBe("All instalments are paid.");
    expect(paid.headline).toBe("Bram Wouters joined Meridian FC");
  });

  it("a completed deal without instalments was paid on completion", () => {
    const v = getDealStatus(deal({ status: "COMPLETED", stage: "COMPLETED" }), viewer());
    expect(v.body).toBe("Paid on completion.");
    expect(v.secondary).toBeUndefined();
  });

  it("a completed loan says until when, and a free signing has no payment line", () => {
    const loan = getDealStatus(deal({ status: "COMPLETED", stage: "COMPLETED", deal_type: "LOAN", loan_end: "2027-05-31" }), viewer());
    expect(loan.headline).toBe("Bram Wouters is on loan at Meridian FC until 31 May 2027");
    expect(getDealStatus(deal({ status: "COMPLETED", stage: "COMPLETED", deal_type: "LOAN" }), viewer({ side: "seller" })).headline)
      .toBe("Bram Wouters joined Meridian FC on loan");
    const free = getDealStatus(deal({ status: "COMPLETED", stage: "COMPLETED", deal_type: "FREE_TRANSFER", seller_club_id: null,
      seller_club: null, agreed_fee: 0 }), viewer());
    expect(free.body).toBeUndefined();
  });
});

describe("getDealStatus: confirmed", () => {
  const confirmed = (over: Partial<Deal> = {}) => deal({ stage: "CONFIRMED", status: "PENDING_COMPLETION", ...over });

  it("a club completes the transfer, with the due date", () => {
    const v = getDealStatus(confirmed({ sla_deadline: "2026-11-24T10:00:00Z" }), viewer());
    expect(v).toMatchObject({ tone: "you", headline: "Complete the transfer", meta: "due 24 Nov 2026" });
    expect(v.primary).toEqual({ kind: "complete", label: "Complete transfer" });
    expect(v.secondary).toEqual({ kind: "open-messages", label: "Message Castlebrook" });
  });

  it("is on hold when he moved in real life, with the window as a strip too", () => {
    const v = getDealStatus(confirmed(), viewer({ realWorld: { hold: "API-Football has him at Arsenal.", window: "The window in England is closed." } }));
    expect(v).toMatchObject({ tone: "hold", overline: "Completion on hold", headline: "Completion waits: Bram Wouters has moved in real life" });
    expect(v.body).toContain("Only completing the transfer waits");
    expect(v.primary).toBeUndefined();
    expect(v.strips).toHaveLength(1);
    expect(v.strips[0].title).toBe("Completes when the transfer window opens");
  });

  it("waits for a closed window", () => {
    const v = getDealStatus(confirmed(), viewer({ realWorld: { hold: null, window: "The window in England is closed." } }));
    expect(v).toMatchObject({ tone: "hold", headline: "Completes when the transfer window opens", strips: [] });
    expect(v.body).toContain("Both clubs are told when it opens");
  });

  it("staff see it is ready", () => {
    expect(getDealStatus(confirmed(), viewer({ side: null, isStaff: true })))
      .toMatchObject({ tone: "info", overline: "Ready to complete" });
  });
});

describe("getDealStatus: paperwork", () => {
  const paperwork = (done = {}, over: Partial<Deal> = {}) => deal({ stage: "PAPERWORK", paperwork: steps(done), ...over });

  it("the buyer signs, and hears the seller already has", () => {
    const v = getDealStatus(paperwork({ agreement_seller: true }, { agreement_signed_by_seller_at: "2026-11-10T09:00:00Z" }), viewer());
    expect(v).toMatchObject({ tone: "you", headline: "Sign the transfer agreement", showChecklist: true });
    expect(v.body).toBe("1 of 4 paperwork steps done. Castlebrook signed the agreement on 10 Nov 2026. When every step is done the deal is confirmed.");
    expect(v.primary).toEqual({ kind: "paperwork", step: "sign-agreement", label: "Mark the agreement signed" });
  });

  it("the buyer records the medical, then submits the registration", () => {
    expect(getDealStatus(paperwork({ agreement_buyer: true, agreement_seller: true }), viewer()).primary)
      .toEqual({ kind: "record-medical", label: "Record medical result" });
    expect(getDealStatus(paperwork({ agreement_buyer: true, agreement_seller: true, medical: true }), viewer()).primary)
      .toEqual({ kind: "paperwork", step: "submit-registration", label: "Mark registration submitted" });
  });

  it("the seller, once signed, waits on the buyer", () => {
    const v = getDealStatus(paperwork({ agreement_seller: true }), viewer({ side: "seller" }));
    expect(v).toMatchObject({ tone: "wait", overline: "Waiting on Meridian FC", headline: "Buying club signs the transfer agreement" });
    expect(v.secondary).toEqual({ kind: "open-messages", label: "Message Meridian FC" });
  });

  it("an agent sees the clubs at work", () => {
    expect(getDealStatus(paperwork(), viewer({ side: null, isAgent: true })))
      .toMatchObject({ tone: "info", headline: "The clubs are completing the paperwork", showChecklist: true });
  });

  it("R-a: a buyer without DEAL_WRITE sees whose move it is, with no actions", () => {
    const v = getDealStatus(paperwork(), viewer({ canWrite: false }));
    expect(v).toMatchObject({ tone: "info", overline: "Your club's move", body: "Your role can see this deal but can't act on it." });
    expect(v.primary).toBeUndefined();
    expect(v.secondary).toBeUndefined();
  });

  it("R-e: a hold and a closed window both show as strips before Confirmed", () => {
    const v = getDealStatus(paperwork(), viewer({ realWorld: { hold: "He moved.", window: "Closed." } }));
    expect(v.strips.map((s) => s.title)).toEqual(["Completion on hold: moved in real life", "Completes when the transfer window opens"]);
  });
});

describe("getDealStatus: personal terms", () => {
  const pt = (t: PersonalTerms | null, over: Partial<Deal> = {}) => deal({ stage: "PERSONAL_TERMS", personal_terms: t, ...over });

  it("the buyer proposes terms", () => {
    expect(getDealStatus(pt(null), viewer({ canSetPersonalTerms: true })))
      .toMatchObject({ tone: "you", headline: "Propose personal terms to Bram Wouters", primary: { kind: "propose-terms" } });
  });

  it("waits on the agent to propose", () => {
    expect(getDealStatus(pt(null, { commission_agent_id: "a", agent }), viewer()))
      .toMatchObject({ tone: "wait", overline: "Waiting on the agent", headline: "Luka Brandt is preparing Bram Wouters's personal terms" });
  });

  it("a club moves on once he agreed", () => {
    const v = getDealStatus(pt(terms({ player_consent: "AGREED" })), viewer({ side: "seller" }));
    expect(v).toMatchObject({ tone: "you", headline: "Move the deal on to paperwork", body: "Bram Wouters accepted £38,000/wk for 4 years." });
    expect(v.primary).toEqual({ kind: "advance", label: "Move on to paperwork" });
  });

  it("the buyer records his answer when he has no account or agent", () => {
    const v = getDealStatus(pt(terms()), viewer({ canRecordConsent: true }));
    expect(v.primary).toEqual({ kind: "record-consent", label: "He agreed" });
    expect(v.secondary).toMatchObject({ kind: "player-consent", agreement: "DECLINED", danger: true });
  });

  it("the agent answers for him", () => {
    const v = getDealStatus(pt(terms({ agent_id: "a", player_has_account: true })), viewer({ side: null, isAgent: true }));
    expect(v).toMatchObject({ tone: "you", headline: "Meridian FC offers Bram Wouters £38,000/wk for 4 years",
      body: "He can answer himself, or you can answer for him." });
    expect(v.primary).toMatchObject({ kind: "player-consent", agreement: "AGREED" });
    expect(v.secondary).toEqual({ kind: "counter-terms", label: "Counter" });
    expect(v.tertiary).toMatchObject({ kind: "player-consent", agreement: "DECLINED", danger: true });
  });

  it("the player side's terms are the buying club's to answer (ADR 0012)", () => {
    const asked = pt(terms({ agent_id: "a", proposed_by: "PLAYER", wage_weekly: 60_000 }),
      { agent: { id: "a", display_name: "Luka Brandt", agency_name: "LB Sports" } });
    const buyer = getDealStatus(asked, viewer());
    expect(buyer).toMatchObject({ tone: "you", headline: "Luka Brandt asks for £60,000/wk for 4 years",
      primary: { kind: "terms-respond", agreement: "AGREED", label: "Accept terms" },
      secondary: { kind: "counter-terms", label: "Counter" },
      tertiary: { kind: "terms-respond", agreement: "DECLINED", label: "Decline", danger: true } });
    expect(getDealStatus(asked, viewer({ side: null, isAgent: true })))
      .toMatchObject({ tone: "wait", overline: "Waiting on Meridian FC", headline: "Meridian FC is answering your terms" });
    expect(getDealStatus(asked, viewer({ side: "seller" })))
      .toMatchObject({ tone: "wait", headline: "Meridian FC is answering Bram Wouters's terms" });
  });

  it("the player himself is sent to his page to answer", () => {
    const v = getDealStatus(pt(terms({ player_has_account: true })), viewer({ side: null, isPlayer: true }));
    expect(v).toMatchObject({ tone: "you", headline: "Answer the personal terms",
      body: "Meridian FC offers £38,000/wk for 4 years. You answer on your player page." });
    expect(v.primary).toEqual({ kind: "open-profile", label: "Answer the terms" });
    expect(v.secondary).toBeUndefined();
  });

  it("a club waits on the player", () => {
    const v = getDealStatus(pt(terms({ player_has_account: true })), viewer({ side: "seller" }));
    expect(v).toMatchObject({ tone: "wait", overline: "Waiting on Bram Wouters", headline: "Bram Wouters hasn't answered the personal terms yet" });
    expect(v.body).toBe("The terms have been sent to the player. The deal moves on once he accepts them.");
  });
});

describe("getDealStatus: agent negotiation", () => {
  const an = (over: Partial<Deal> = {}) => deal({ stage: "AGENT_NEGOTIATION", agent, ...over });
  const agentViewer = (n: AgentNegotiation | null) => viewer({ side: null, isAgent: true, negotiation: n });

  it("the agent proposes, waits, and answers the club's counter", () => {
    expect(getDealStatus(an(), agentViewer(neg({ commission_pct: null, commission_amount: null }))).headline).toBe("Propose your commission");
    expect(getDealStatus(an(), agentViewer(neg()))).toMatchObject({ tone: "wait", body: "You asked for 6.0% (£324,000)." });
    const countered = neg({ proposed_by: "BUYER", commission_pct: 0.04, commission_amount: 216_000 });
    expect(getDealStatus(an(), agentViewer(countered))).toMatchObject({ tone: "you",
      headline: "Meridian FC countered with 4.0% (£216,000)", primary: { kind: "agent-accept", label: "Accept counter" } });
    expect(getDealStatus(an(), viewer({ negotiation: countered })))
      .toMatchObject({ tone: "wait", overline: "Waiting on the agent", headline: "Luka Brandt is answering your counter of 4.0% (£216,000)" });
  });

  it("once agreed, the agent and the buyer move on; the seller waits (Q1)", () => {
    const agreed = neg({ club_agreement: "AGREED" });
    for (const v of [agentViewer(agreed), viewer({ negotiation: agreed })]) {
      expect(getDealStatus(an(), v)).toMatchObject({ tone: "you", headline: "Move the deal on to personal terms",
        primary: { kind: "advance", label: "Move on to personal terms" } });
    }
    const seller = getDealStatus(an(), viewer({ side: "seller", negotiation: agreed }));
    expect(seller).toMatchObject({ tone: "wait", headline: "Meridian FC agreed the agent's commission" });
    expect(seller.primary).toBeUndefined();
  });

  it("the buyer answers a pending proposal; the seller waits", () => {
    const v = getDealStatus(an(), viewer({ negotiation: neg({ additional_conditions: "Paid in two parts" }) }));
    expect(v).toMatchObject({ tone: "you", headline: "Luka Brandt asks for 6.0% (£324,000)",
      body: "Paid by the buying club. Conditions: Paid in two parts" });
    expect(v.primary).toMatchObject({ kind: "commission-respond", agreement: "AGREED", label: "Accept proposal" });
    expect(v.secondary).toEqual({ kind: "commission-counter", label: "Counter" });
    expect(v.tertiary).toMatchObject({ kind: "commission-respond", agreement: "DECLINED", danger: true });
    expect(getDealStatus(an(), viewer({ side: "seller", negotiation: neg() })))
      .toMatchObject({ tone: "wait", headline: "Meridian FC is answering the agent's commission proposal" });
  });

  it("with no negotiation record, a club waits on the agent", () => {
    expect(getDealStatus(an(), viewer({ negotiation: undefined })))
      .toMatchObject({ tone: "wait", headline: "Luka Brandt hasn't proposed his commission yet" });
  });
});

describe("getDealStatus: agreement", () => {
  it("a club moves it on to personal terms (D8)", () => {
    const v = getDealStatus(deal(), viewer());
    expect(v.primary).toEqual({ kind: "advance", label: "Move on to personal terms" });
    expect(v.body).toBe("Both clubs agreed £5.4M. Either club can move it on; Bram Wouters then has to agree his personal terms.");
  });

  it("with no selling club, the buyer moves it on", () => {
    const v = getDealStatus(deal({ seller_club_id: null, seller_club: null, deal_type: "FREE_TRANSFER", agreed_fee: 0 }), viewer());
    expect(v.body).toBe("Meridian FC agreed to sign Bram Wouters. Meridian FC moves it on; Bram Wouters then has to agree his personal terms.");
    expect(v.secondary).toEqual({ kind: "open-messages", label: "Open messages" });
  });

  it("anyone else sees the stage", () => {
    expect(getDealStatus(deal(), viewer({ side: null, isStaff: true })))
      .toMatchObject({ tone: "info", headline: "This deal is at agreement" });
  });
});

describe("getDealStatus: rules", () => {
  it("R-b: waiting three days reads as idle", () => {
    const v = getDealStatus(deal({ stage: "PAPERWORK", paperwork: steps({ agreement_seller: true }), updated_at: "2026-11-06T10:00:00Z" }), viewer({ side: "seller" }));
    expect(v.meta).toBe("4 days without movement");
  });
});

describe("dealStages", () => {
  it("always includes personal terms (D7)", () => {
    expect(dealStages(deal(), null)).toEqual(["AGREEMENT", "PERSONAL_TERMS", "PAPERWORK", "CONFIRMED", "COMPLETED"]);
  });

  it("keeps the agent stage once commission is done", () => {
    expect(dealStages(deal({ stage: "PAPERWORK", agent }), null)).toContain("AGENT_NEGOTIATION");
  });

  it("notes what each stage agreed", () => {
    const d = deal({ stage: "PAPERWORK", agreed_wage_weekly: 38_000, agent_commission_pct: 0.06, agent });
    expect(stageNote(d, null, "AGREEMENT", "done")).toBe("Clubs agreed £5.4M");
    expect(stageNote(d, null, "AGENT_NEGOTIATION", "done")).toBe("Agent agreed 6.0%");
    expect(stageNote(d, null, "PERSONAL_TERMS", "done")).toBe("Bram agreed £38,000/wk");
    expect(stageNote(d, null, "PAPERWORK", "now")).toBe("Paperwork 0 of 4");
  });
});
