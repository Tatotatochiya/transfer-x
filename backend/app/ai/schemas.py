from pydantic import BaseModel


class AIConfigResponse(BaseModel):
    model: str
    provider: str
    anthropic_configured: bool
    openai_configured: bool
    deepseek_configured: bool


class RecommendedProfile(BaseModel):
    position: str
    age_range: str
    priority: str  # "high" | "medium" | "low"
    reason: str


class SquadAnalysisResponse(BaseModel):
    summary: str
    positional_gaps: list[str]
    age_risks: list[str]
    contract_risks: list[str]
    recommended_profiles: list[RecommendedProfile]
    cached: bool = False


class PlayerFitResponse(BaseModel):
    fit_score: int
    summary: str
    strengths: list[str]
    concerns: list[str]
    cached: bool = False


class PlayerRecommendation(BaseModel):
    player_id: str
    sale_id: str | None = None
    name: str
    position: str | None
    fit_score: int
    reason: str


class MarketRecommendationsResponse(BaseModel):
    recommendations: list[PlayerRecommendation]
    total_candidates: int
    cached: bool = False


class ShortlistPlayerAssessment(BaseModel):
    player_id: str
    name: str
    fit_priority: str  # "high" | "medium" | "low"
    addresses_gap: bool
    reason: str


class ShortlistReviewResponse(BaseModel):
    summary: str
    overall_verdict: str  # "strong" | "adequate" | "weak"
    player_assessments: list[ShortlistPlayerAssessment]
    top_picks: list[str]
    missing_positions: list[str]
    cached: bool = False


class NLSearchRequest(BaseModel):
    query: str


class ParsedFilters(BaseModel):
    position: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_form_score: float | None = None
    nationalities: list[str] | None = None
    min_height_cm: int | None = None
    open_to_offers: bool | None = None
    interpreted_as: str


class NLPlayerSearchResult(BaseModel):
    player_id: str
    name: str
    age: int | None
    position: str | None
    nationality: str | None
    current_club: str | None
    form_score: float | None
    open_to_offers: bool


class NLSearchResponse(BaseModel):
    players: list[NLPlayerSearchResult]
    filters: ParsedFilters
    total: int


class AIUsageStats(BaseModel):
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    by_endpoint: dict[str, dict]
    note: str


class AIRateLimitStatus(BaseModel):
    used: int
    limit: int
    remaining: int


class PromptInfo(BaseModel):
    key: str
    content: str
    is_overridden: bool
    default_content: str


class PromptOverrideRequest(BaseModel):
    content: str
