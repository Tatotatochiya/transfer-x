"""Prompt templates with in-memory versioning. Use get_prompt(key) everywhere."""

SYSTEM_SCOUT = (
    "You are an expert football analyst and scout for a football transfer management platform. "
    "Analyse squad data, player statistics, and transfer market information to provide actionable insights. "
    "Be concise, specific, and focus on the most impactful observations. "
    "Always respond with valid JSON when instructed to do so."
)

SQUAD_ANALYSIS_USER = """\
Analyse the following squad and provide a structured report.

Squad data:
{squad_json}

Return a JSON object with these exact fields:
- "summary": string (2-3 sentence overview of squad strength)
- "positional_gaps": list of strings (positions that are thin or missing depth)
- "age_risks": list of strings (age-related concerns, e.g. ageing starters, no youth)
- "contract_risks": list of strings (players with contracts expiring within 6 months)
- "recommended_profiles": list of objects, each with:
    - "position": string
    - "age_range": string (e.g. "22-27")
    - "priority": "high" | "medium" | "low"
    - "reason": string
"""

PLAYER_FIT_USER = """\
Evaluate how well the following player fits the squad.

Player profile:
{player_json}

Current squad context:
{squad_json}

Return a JSON object with:
- "fit_score": integer 0-100
- "summary": string (2-3 sentences)
- "strengths": list of strings (why this player suits the squad)
- "concerns": list of strings (potential issues or redundancies)
"""

SHORTLIST_REVIEW_USER = """\
Review the following scouting shortlist against the club's current squad and provide a structured assessment.

Current squad:
{squad_json}

Shortlisted players (with user-set priorities 1=highest, 5=lowest):
{shortlist_json}

Return a JSON object with:
- "summary": string (2-3 sentences — overall quality of the shortlist)
- "overall_verdict": "strong" | "adequate" | "weak"
- "player_assessments": list of objects for each shortlisted player:
    - "player_id": string (UUID, must match input exactly)
    - "name": string
    - "fit_priority": "high" | "medium" | "low" (your recommendation, may differ from user priority)
    - "addresses_gap": boolean (does this signing fix a real squad need?)
    - "reason": string (1-2 sentences)
- "top_picks": list of player names (max 3, the ones to pursue first)
- "missing_positions": list of positions not covered by the shortlist but needed by the squad
"""

NL_SEARCH_PARSE = """\
Parse the following natural language player search query into structured filters.

Query: {query}

Return ONLY a valid JSON object with these fields (use null for anything not specified):
{{
  "position": "GK" | "DEF" | "MID" | "FWD" | null,
  "min_age": integer | null,
  "max_age": integer | null,
  "min_form_score": number | null,
  "nationalities": ["country name", ...] | null,
  "min_height_cm": integer | null,
  "open_to_offers": true | false | null,
  "min_value": number | null,
  "max_value": number | null,
  "contract_ends_within_months": integer | null,
  "max_wage_weekly": number | null,
  "league": "league name" | null,
  "interpreted_as": "plain English summary of what you understood"
}}

Mappings to apply:
- Positions: goalkeeper→GK, defender/left-back/right-back/centre-back/cb/lb/rb→DEF, midfielder/cm/dm/am/winger→MID, forward/striker/attacker/cf/st→FWD
- Form thresholds: poor <40, average 40-60, good 60-75, excellent >75
- Age terms: young/youth→max_age 24, experienced→min_age 28, veteran→min_age 32, prime→min_age 24 max_age 30
- Height: 6ft=183cm, 6ft1=185cm, 6ft2=188cm, 6ft3=190cm, 6ft4=193cm, 6ft5=196cm, 5ft11=180cm, 5ft10=178cm; "tall"→min_height_cm 185; convert any feet/inches to cm
- Nationalities: always use full country names (England, Spain, Italy, France, Germany, Brazil, Argentina…); if multiple countries mentioned, list them all in the array
- Price or value, in pounds as a plain number: "under £10m"→max_value 10000000, "£5-8m"→min_value 5000000 and
  max_value 8000000, "cheap"/"bargain"→max_value 5000000, "free"/"free agent"→max_value 0
- Contract: "out of contract next summer"/"contract expiring"/"running down his deal"→contract_ends_within_months 12,
  "within 6 months"→6
- Wages, in pounds a week: "earning under £50k a week"→max_wage_weekly 50000
- League: the competition named ("Premier League", "Championship", "La Liga", "Serie A", "Bundesliga", "Ligue 1")
"""

MARKET_RECOMMENDATIONS_USER = """\
Given the squad context and the available players on the market, recommend the best fits.

Squad context:
{squad_json}

Available players:
{market_json}

Return a JSON array of up to 10 recommended players, each with:
- "player_id": string (UUID)
- "sale_id": string (UUID)
- "name": string
- "position": string
- "fit_score": integer 0-100
- "reason": string (1-2 sentences)
"""


# ── Workflow assistant (offers, deals, briefing, listings, Ask) ──────────────
#
# Every figure in these prompts' input was computed by TransferX from data the
# viewing club is allowed to see. The model phrases and recommends; it does not
# supply numbers of its own. Keep "Only use figures given" in any override.

SYSTEM_ADVISOR = (
    "You are the transfer assistant inside TransferX, a platform professional football clubs use to buy, "
    "sell and loan players. You advise one club, the viewer. "
    "Only use the facts and figures given to you; never invent a number, a club, a player or an event. "
    "Money is in the currency given; write amounts compactly (e.g. £12.5m, £80k/wk). "
    "Be brief, specific and practical, like a trusted sporting-director's analyst. "
    "You recommend; the club decides and acts. "
    "Never pad with generic advice such as 'act promptly', 'avoid delays', 'communicate clearly' or "
    "'delay risks the deal': every tip must rest on a specific fact given to you (a name, figure, date, "
    "clause or step). If you have nothing specific to add, give fewer tips or none. "
    "Write for people, not code: never quote field names, status codes or true/false values "
    "(say 'they haven't replied yet', not 'status is SENT and your_turn is false'). "
    "Always respond with a single valid JSON object and nothing else."
)

OFFER_ADVICE_USER = """\
The viewer is the {role} club in this negotiation. Facts (computed by TransferX; the viewer may see all of them):
{facts_json}

Rule-based checks already raised on the current terms:
{checks_json}

Advise the viewer on their next move. Return JSON:
- "summary": string, 1-2 sentences on where the negotiation stands for the viewer
- "recommendation": one of "accept", "counter", "reject", "wait" ("wait" when it is not the viewer's turn)
- "suggested_terms": object or null. Only when recommending "counter": the terms to propose, using only these
  keys, each a number or null for unchanged: "fee_amount", "wage_weekly", "contract_years", "sell_on_pct"
  (a fraction, 0.1 = 10%), "loan_fee", "wage_split_pct" (fraction the borrowing club pays), "option_to_buy".
  Anchor every figure to the facts (current terms, model range, guide price, budget).
- "reasons": list of 2-4 short strings
- "watch_outs": list of 0-3 short strings
"""

NEGOTIATION_SUMMARY_USER = """\
Summarise this negotiation for the {role} club. Chronological history (computed by TransferX):
{facts_json}

"moves_by_you" and "moves_by_them" already list who changed what; do not reassign a move to the other side.

Return JSON:
- "summary": string, 2-3 sentences: how the terms moved and where they stand now
- "gap": string or null, the remaining difference between the sides in one phrase (e.g. "£2.5m on the fee")
- "their_moves": list of short strings, rephrasing "moves_by_them" (empty if it is empty)
- "your_moves": list of short strings, rephrasing "moves_by_you" (empty if it is empty)
"""

DEAL_BRIEF_USER = """\
Brief the {role} club on this transfer's next steps. Facts, including the outstanding steps already worked out
by TransferX, with who owns each:
{facts_json}

Return JSON:
- "headline": string, one sentence: what the deal is waiting on and who must act
- "advice": list of 0-2 short strings. Only tips that add something the steps do not already say, each tied
  to a fact above (a figure, date, clause, consent state or idle days). Do not restate a step, and do not
  mention deadlines when none is given. An empty list is a good answer when the steps say it all.
"""

CLUB_BRIEFING_USER = """\
Write this morning's briefing for {club_name}. Facts (their own data only):
{facts_json}

Return JSON:
- "headline": string, one sentence on the day
- "focus": string, the single most important thing to do today and why
- "points": list of 2-5 short strings covering what needs them and what changed in the last 24 hours
"""

LISTING_ADVICE_USER = """\
The viewer's club is considering listing (or re-pricing) one of its players. Facts, including a guide price
TransferX computed from the fee model and comparable completed transfers:
{facts_json}

Return JSON:
- "summary": string, 1-2 sentences
- "availability": one of "TRANSFER", "LOAN", "EITHER", with the loan option only if the facts support it
  (young, low minutes, long contract)
- "reasons": list of 2-4 short strings explaining the guide price and availability
- "tips": list of 0-3 short strings (e.g. for a listing with no offers: lower the price, open to loans)
If there is no computed guide price, the club sets the price from its own view — a guide price is optional and
listing without one simply invites offers. Never tell the club to wait, not to list, or that it must set a price
first.
"""

POTENTIAL_BUYERS_USER = """\
The viewer's club wants to know which clubs on TransferX might want its player. Candidate clubs, each with the
squad facts TransferX found (public squad information only):
{facts_json}

Return JSON:
- "summary": string, one sentence
- "clubs": list of up to 5 objects, best first, each with "club_id" (copied exactly from the facts) and
  "reason" (one sentence grounded in that club's facts)
"""

ASK_USER = """\
A member of {club_name} asks: "{question}"

Everything TransferX may show them that could be relevant (their own club's data only):
{facts_json}

Answer only from these facts; if they do not contain the answer, say so plainly. Return JSON:
- "answer": string, 1-4 sentences
- "links": list of 0-4 objects {{"label": string, "path": string}}, where every path is copied exactly from a
  "path" field in the facts
"""

ASK_LITE_USER = """\
A member of {club_name} asks, in Lite mode: "{question}"

Everything TransferX may show them that could be relevant (their own club's data only):
{facts_json}

Answer only from these facts; if they do not contain the answer, say so plainly. Write plain British English for a
busy director: at most three sentences, money like "£8m" or "£35k a week", and no internal terms (no stage or
status codes, no enum names). Return JSON:
- "answer": string
- "links": list of 0-3 objects {{"label": string, "path": string}}, every path copied exactly from a "path" field
  in the facts. Prefer Lite pages (paths starting "/lite") when one fits.
- "proposal": null, unless they ask TransferX to do something it can prepare for them to confirm. Then an object:
  {{"kind": "bid" | "counter" | "accept" | "reject",
    "player": the player's name as they wrote it (for "bid"),
    "offer_path": a "path" copied exactly from an offer in the facts (for "counter", "accept", "reject"),
    "amount": number in pounds (for "bid" and "counter"; null if they gave none)}}
  Nothing is sent: they check it on a card and confirm it themselves. For a bid the player need not appear in the
  facts: TransferX finds him and checks the club and price itself, so give the proposal with his name as they
  wrote it, and keep the answer to one sentence saying it is ready to check. If TransferX cannot match it, it
  shows them links instead.
"""

DRAFT_MESSAGE_USER = """\
Draft a message for {club_name} to send. It is {purpose}.
Facts (computed by TransferX; everything here may be said to the recipients):
{facts_json}

What the user wants it to say (may be empty; follow it when given): "{intent}"

Return JSON:
- "text": the message, 2-5 sentences, ready to send. Plain, courteous, professional British English, written as
  the club ("we"). Money like "£6m" or "£35k a week". Use only names and figures from the facts; refer to a club
  shown as undisclosed only as it is shown. No placeholders in brackets, no sign-off name, and do not commit the
  club to anything the facts or the user's note do not support.
"""

LITE_BUY_REASONS_USER = """\
A sporting director asked for a player. TransferX has already chosen these players and computed every figure:
{facts_json}

For each player write one short sentence (at most 20 words) on why he fits this club, in plain British English,
money written like "£6m". Use only the facts given. Return JSON:
- "reasons": object mapping each "player_id" (copied exactly) to its sentence
"""


# ── Versioning ────────────────────────────────────────────────────────────────

_DEFAULTS: dict[str, str] = {
    "SYSTEM_SCOUT": SYSTEM_SCOUT,
    "SQUAD_ANALYSIS_USER": SQUAD_ANALYSIS_USER,
    "PLAYER_FIT_USER": PLAYER_FIT_USER,
    "MARKET_RECOMMENDATIONS_USER": MARKET_RECOMMENDATIONS_USER,
    "SHORTLIST_REVIEW_USER": SHORTLIST_REVIEW_USER,
    "NL_SEARCH_PARSE": NL_SEARCH_PARSE,
    "SYSTEM_ADVISOR": SYSTEM_ADVISOR,
    "OFFER_ADVICE_USER": OFFER_ADVICE_USER,
    "NEGOTIATION_SUMMARY_USER": NEGOTIATION_SUMMARY_USER,
    "DEAL_BRIEF_USER": DEAL_BRIEF_USER,
    "CLUB_BRIEFING_USER": CLUB_BRIEFING_USER,
    "LISTING_ADVICE_USER": LISTING_ADVICE_USER,
    "POTENTIAL_BUYERS_USER": POTENTIAL_BUYERS_USER,
    "ASK_USER": ASK_USER,
    "LITE_BUY_REASONS_USER": LITE_BUY_REASONS_USER,
    "DRAFT_MESSAGE_USER": DRAFT_MESSAGE_USER,
    "ASK_LITE_USER": ASK_LITE_USER,
}

_overrides: dict[str, str] = {}


def get_prompt(key: str) -> str:
    """Return current prompt for key — override takes precedence over default."""
    if key in _overrides:
        return _overrides[key]
    if key not in _DEFAULTS:
        raise KeyError(f"Unknown prompt key: {key!r}")
    return _DEFAULTS[key]


def set_override(key: str, content: str) -> None:
    if key not in _DEFAULTS:
        raise KeyError(f"Unknown prompt key: {key!r}")
    _overrides[key] = content


def reset_override(key: str) -> None:
    _overrides.pop(key, None)


def list_prompts() -> list[dict]:
    return [
        {
            "key": key,
            "content": get_prompt(key),
            "is_overridden": key in _overrides,
            "default_content": _DEFAULTS[key],
        }
        for key in _DEFAULTS
    ]
