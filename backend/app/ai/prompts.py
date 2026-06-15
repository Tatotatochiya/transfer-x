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
  "interpreted_as": "plain English summary of what you understood"
}}

Mappings to apply:
- Positions: goalkeeper→GK, defender/left-back/right-back/centre-back/cb/lb/rb→DEF, midfielder/cm/dm/am/winger→MID, forward/striker/attacker/cf/st→FWD
- Form thresholds: poor <40, average 40-60, good 60-75, excellent >75
- Age terms: young/youth→max_age 24, experienced→min_age 28, veteran→min_age 32, prime→min_age 24 max_age 30
- Height: 6ft=183cm, 6ft1=185cm, 6ft2=188cm, 6ft3=190cm, 6ft4=193cm, 6ft5=196cm, 5ft11=180cm, 5ft10=178cm; "tall"→min_height_cm 185; convert any feet/inches to cm
- Nationalities: always use full country names (England, Spain, Italy, France, Germany, Brazil, Argentina…); if multiple countries mentioned, list them all in the array
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

# ── Versioning ────────────────────────────────────────────────────────────────

_DEFAULTS: dict[str, str] = {
    "SYSTEM_SCOUT": SYSTEM_SCOUT,
    "SQUAD_ANALYSIS_USER": SQUAD_ANALYSIS_USER,
    "PLAYER_FIT_USER": PLAYER_FIT_USER,
    "MARKET_RECOMMENDATIONS_USER": MARKET_RECOMMENDATIONS_USER,
    "SHORTLIST_REVIEW_USER": SHORTLIST_REVIEW_USER,
    "NL_SEARCH_PARSE": NL_SEARCH_PARSE,
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
