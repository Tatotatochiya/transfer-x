import type {
  BidStatus,
  ClubRole,
  DealStage,
  DealStatus,
  InterestLevel,
  InterestStage,
  NotificationType,
  OfferEventType,
  OfferStatus,
  PlayerPosition,
  PlayerStatus,
  PlayerVisibility,
  SaleStatus,
  SaleType,
} from "./enums";

// ── Shared ────────────────────────────────────────────────────────────────────

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ── Clubs ─────────────────────────────────────────────────────────────────────

export interface ClubFinance {
  transfer_budget_total: number;
  wage_budget_total_weekly: number;
  transfer_reserved: number;
  wage_reserved_weekly: number;
  transfer_committed: number;
  transfer_spent: number;
  wage_committed_weekly: number;
  transfer_remaining: number;
  wage_remaining_weekly: number;
  updated_at: string;
}

export interface Club {
  id: string;
  name: string;
  country: string | null;
  city: string | null;
  league_name: string | null;
  crest_url: string | null;
  role: ClubRole;
  created_at: string;
  finance: ClubFinance | null;
  my_role?: string; // OWNER | MANAGER | READONLY — only present on /clubs/me
}

export interface ClubPublic {
  id: string;
  name: string;
  country: string | null;
  city: string | null;
  league_name: string | null;
  crest_url: string | null;
  role: ClubRole;
  created_at: string;
}

// ── World teams ───────────────────────────────────────────────────────────────

export interface WorldTeam {
  id: string;
  vendor: string;
  vendor_id: string;
  name: string;
  country: string | null;
  league_name: string | null;
  crest_url: string | null;
  season: string | null;
  created_at: string;
}

export interface WorldTeamMinimal {
  id: string;
  vendor_id: string;
  name: string;
  crest_url: string | null;
  country: string | null;
  league_name: string | null;
}

// ── Players ───────────────────────────────────────────────────────────────────

export interface ClubMinimal {
  id: string;
  name: string;
  crest_url: string | null;
}

export interface Contract {
  id: string;
  club_id: string;
  start_date: string | null;
  end_date: string | null;
  wage_weekly: number | null;
  release_clause: number | null;
  club_valuation: number | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

export interface Player {
  id: string;
  name: string;
  firstname: string | null;
  lastname: string | null;
  age: number | null;
  nationality: string | null;
  position: PlayerPosition | null;
  status: PlayerStatus;
  visibility: PlayerVisibility;
  open_to_offers: boolean;
  photo_url: string | null;
  team_name: string | null;
  current_club: ClubMinimal | null;
  world_team: WorldTeamMinimal | null;
  height: string | null;
  weight: string | null;
  birth_date: string | null;
  birth_place: string | null;
  birth_country: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActiveDealStub {
  id: string;
  status: "IN_PROGRESS" | "COMPLETED";
  stage: string | null;
  buyer_club: ClubMinimal | null;
  seller_club: ClubMinimal | null;
  agreed_fee: number | null;
  completed_at: string | null;
}

export interface PlayerDetail extends Player {
  active_contract: Contract | null;
  active_deal: ActiveDealStub | null;
}

// ── Sales ─────────────────────────────────────────────────────────────────────

export interface PlayerSummary {
  id: string;
  name: string;
  position: string | null;
}

export interface SellerClubSummary {
  id: string;
  name: string;
}

export interface Sale {
  id: string;
  player_id: string;
  seller_club_id: string;
  sale_type: SaleType;
  asking_price: number | null;
  reserve_price: number | null;
  min_increment: number;
  deadline: string | null;
  notes: string | null;
  status: SaleStatus;
  created_at: string;
  updated_at: string;
  player: PlayerSummary | null;
  seller_club: SellerClubSummary | null;
  // auction summary fields
  bid_count: number;
  best_bid: number | null;
  minimum_next_bid: number | null;
  reserve_met: boolean;
}

export interface Bid {
  id: string;
  sale_id: string;
  buyer_club_id: string;
  amount: number;
  wage_offer_weekly: number | null;
  notes: string | null;
  status: BidStatus;
  created_at: string;
  updated_at: string;
  buyer_club: { id: string; name: string } | null;
}

export interface DealStub {
  id: string;
  sale_id: string | null;
  bid_id: string | null;
  buyer_club_id: string;
  seller_club_id: string;
  player_id: string;
  agreed_fee: number;
  agreed_wage_weekly: number | null;
  status: string;
  stage: string;
  created_at: string;
  updated_at: string;
}

// ── Offers ────────────────────────────────────────────────────────────────────

export interface ClubSummary {
  id: string;
  name: string;
}

export interface OfferMessage {
  id: string;
  offer_id: string;
  sender_club_id: string | null;
  body: string;
  created_at: string;
  sender_club: ClubSummary | null;
}

export interface OfferEvent {
  id: string;
  offer_id: string;
  event_type: OfferEventType;
  actor_club_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Offer {
  id: string;
  player_id: string;
  sale_id: string | null;
  from_club_id: string;
  to_club_id: string | null;
  last_actor_club_id: string | null;
  fee_amount: number | null;
  wage_weekly: number | null;
  contract_years: number | null;
  contract_end_date: string | null;
  add_ons: Record<string, unknown>;
  status: OfferStatus;
  expires_at: string | null;
  last_action_at: string;
  created_at: string;
  player: PlayerSummary | null;
  from_club: ClubSummary | null;
  to_club: ClubSummary | null;
  messages: OfferMessage[];
  events: OfferEvent[];
}

// ── Deals ─────────────────────────────────────────────────────────────────────

export interface DealNote {
  id: string;
  deal_id: string;
  author_club_id: string | null;
  body: string;
  created_at: string;
  author_club: ClubSummary | null;
}

export interface Deal {
  id: string;
  sale_id: string | null;
  bid_id: string | null;
  offer_id: string | null;
  buyer_club_id: string;
  seller_club_id: string | null;
  player_id: string;
  agreed_fee: number;
  agreed_wage_weekly: number | null;
  status: DealStatus;
  stage: DealStage;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  is_auction_deal: boolean;
  buyer_club: ClubSummary | null;
  seller_club: ClubSummary | null;
  player: PlayerSummary | null;
  deal_notes: DealNote[];
}

// ── Transfer activity ─────────────────────────────────────────────────────────

export interface TransferActivity {
  id: string;
  player: PlayerSummary | null;
  buyer_club: ClubSummary | null;
  seller_club: ClubSummary | null;
  agreed_fee: number;
  is_auction_deal: boolean;
  completed_at: string | null;
  created_at: string;
}

// ── Transfer window ───────────────────────────────────────────────────────────

export interface TransferWindowResponse {
  id: string;
  name: string;
  opens_at: string;
  closes_at: string;
  is_open: boolean;
  created_at: string;
}

export interface TransferWindowStatus {
  enforced: boolean;
  is_open: boolean;
  current_window: TransferWindowResponse | null;
  next_window: TransferWindowResponse | null;
}

export interface ShortlistHit {
  player_id: string;
  player_name: string;
  position: string | null;
  shortlist_name: string;
  sale_id: string;
  sale_type: string;
  asking_price: number | null;
  deadline: string | null;
}

export interface ExpiringContractItem {
  player_id: string;
  player_name: string;
  position: string | null;
  end_date: string;
  days_remaining: number;
}

// ── Transfer analytics ────────────────────────────────────────────────────────

export interface ClubTransferStat {
  club: ClubSummary;
  count: number;
  total_spend: number;
}

export interface PositionBreakdown {
  position: string;
  count: number;
  total_spend: number;
}

export interface OngoingStats {
  total_count: number;
  by_stage: Record<string, number>;
  total_committed_fees: number;
}

export interface CompletedStats {
  total_count: number;
  total_spend: number;
  avg_fee: number | null;
  highest_fee_deal: TransferActivity | null;
  top_transfers: TransferActivity[];
  most_active_buyer: ClubTransferStat | null;
  most_active_seller: ClubTransferStat | null;
  by_position: PositionBreakdown[];
  auction_count: number;
  offer_count: number;
  recent_30d_count: number;
  recent_30d_spend: number;
}

export interface TransferAnalytics {
  completed: CompletedStats;
  ongoing: OngoingStats;
}

// ── Scouting ──────────────────────────────────────────────────────────────────

export interface ShortlistItem {
  id: string;
  shortlist_id: string;
  player_id: string;
  priority: number;
  notes: string | null;
  created_at: string;
  player: {
    id: string;
    name: string;
    position: string | null;
    status: string | null;
    open_to_offers: boolean;
    team_name: string | null;
  } | null;
}

export interface Shortlist {
  id: string;
  club_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  items: ShortlistItem[];
}

export interface ShortlistSummary {
  id: string;
  club_id: string;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface PlayerInterest {
  id: string;
  club_id: string;
  player_id: string;
  level: InterestLevel;
  stage: InterestStage;
  notes: string | null;
  last_touched_at: string;
  created_at: string;
  player: {
    id: string;
    name: string;
    position: string | null;
    status: string | null;
    open_to_offers: boolean;
    team_name: string | null;
  } | null;
}

export interface TargetPlayer {
  player_id: string;
  name: string;
  position: string | null;
  status: string;
  open_to_offers: boolean;
  on_shortlists: string[];
  interest_level: string | null;
  interest_stage: string | null;
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export interface AdminUser {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface AdminClubFinance {
  transfer_budget_total: number;
  wage_budget_total_weekly: number;
  transfer_reserved: number;
  wage_reserved_weekly: number;
  transfer_committed: number;
  transfer_spent: number;
  wage_committed_weekly: number;
  transfer_remaining: number;
  wage_remaining_weekly: number;
}

export interface AdminClub {
  id: string;
  user_id: string;
  name: string;
  country: string | null;
  city: string | null;
  league_name: string | null;
  crest_url: string | null;
  role: string;
  created_at: string;
}

export interface AdminClubDetail extends AdminClub {
  finance: AdminClubFinance | null;
}

export interface AdminDeal {
  id: string;
  player: { id: string; name: string; position: string | null } | null;
  buyer_club: { id: string; name: string } | null;
  seller_club: { id: string; name: string } | null;
  agreed_fee: number;
  status: DealStatus;
  stage: DealStage;
  created_at: string;
  completed_at: string | null;
}

export interface AdminStats {
  total_users: number;
  total_clubs: number;
  total_players: number;
  active_sales: number;
  open_offers: number;
  active_deals: number;
  deals_by_stage: Record<string, number>;
}

export interface ActivityItem {
  event_type: string;
  message: string;
  link: string | null;
  entity_id: string | null;
  occurred_at: string;
}

export interface HealthIssue {
  severity: "critical" | "warning" | "info";
  category: string;
  message: string;
  count: number;
  details: { id: string; label: string }[];
}

export interface HealthReport {
  issues: HealthIssue[];
  checked_at: string;
  healthy: boolean;
}

export interface ClubStaffUser {
  id: string;
  email: string;
  is_active: boolean;
}

export interface ClubStaff {
  id: string;
  club_id: string;
  user_id: string;
  role: "MANAGER" | "READONLY";
  created_at: string;
  user: ClubStaffUser | null;
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export interface PlayerStats {
  id: string;
  player_id: string;
  vendor: string;
  league_id: string | null;
  season: string | null;
  // Core
  goals: number;
  assists: number;
  appearances: number;
  avg_rating: number | null;
  form_score: number | null;
  minutes: number | null;
  // Team context
  team_vendor_id: string | null;
  team_name: string | null;
  // Games detail
  lineups: number | null;
  shirt_number: number | null;
  // Shots
  shots_total: number | null;
  shots_on_target: number | null;
  // Passing
  key_passes: number | null;
  pass_accuracy: number | null;
  // Defending
  tackles_total: number | null;
  interceptions: number | null;
  blocks: number | null;
  // Duels
  duels_total: number | null;
  duels_won: number | null;
  // Dribbles
  dribbles_attempts: number | null;
  dribbles_success: number | null;
  // Discipline
  yellow_cards: number | null;
  red_cards: number | null;
  fouls_committed: number | null;
  fouls_drawn: number | null;
  // Goalkeeper
  saves: number | null;
  goals_conceded: number | null;
  // Penalty
  penalty_scored: number | null;
  penalty_missed: number | null;
  penalty_won: number | null;
  penalty_committed: number | null;
  penalty_saved: number | null;
  // Cards
  cards_yellowred: number | null;
  // Substitutions
  substitutes_in: number | null;
  substitutes_out: number | null;
  substitutes_bench: number | null;
  // Additional
  passes_total: number | null;
  dribbles_past: number | null;
  position_played: string | null;
  updated_at: string;
}

export interface PlayerForm {
  id: string;
  player_id: string;
  form_score: number;
  games_considered: number;
  key_metrics: Record<string, unknown> | null;
  trend: number | null;
  last_updated: string;
}

// ── Player search views ───────────────────────────────────────────────────────

export interface PlayerSearchView {
  id: string;
  club_id: string;
  name: string;
  filters: Record<string, unknown>;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

// ── Notifications ─────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  recipient_user_id: string;
  type: NotificationType;
  message: string;
  link: string | null;
  is_read: boolean;
  related_player_id: string | null;
  related_club_id: string | null;
  created_at: string;
}

export interface UnreadCount {
  count: number;
}

export interface NotificationPreferenceItem {
  type: string;
  enabled: boolean;
}

export interface NotificationPreferencesResponse {
  preferences: NotificationPreferenceItem[];
}

// ── Player career ─────────────────────────────────────────────────────────────

export interface PlayerTransfer {
  transfer_date: string | null;
  transfer_type: string | null;
  team_in_vendor_id: string | null;
  team_in_name: string | null;
  team_in_crest_url: string | null;
  team_out_vendor_id: string | null;
  team_out_name: string | null;
  team_out_crest_url: string | null;
  fee_display: string | null;
}

export interface PlayerInjury {
  league_name: string | null;
  season: string | null;
  fixture_date: string | null;
  injury_type: string | null;
  reason: string | null;
  games_absent: number | null;
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

export interface Fixture {
  fixture_vendor_id: number;
  league_id: number | null;
  league_name: string | null;
  round: string | null;
  home_team_vendor_id: number;
  home_team_name: string;
  home_team_crest_url: string | null;
  away_team_vendor_id: number;
  away_team_name: string;
  away_team_crest_url: string | null;
  kickoff_at: string | null;
  status_short: string;
  status_long: string | null;
  home_goals: number | null;
  away_goals: number | null;
  venue_name: string | null;
}

// ── Order book ────────────────────────────────────────────────────────────────

export interface OrderBookClubSummary {
  id: string;
  name: string;
  crest_url: string | null;
}

export interface OrderBookEntry {
  rank: number;
  kind: "bid" | "offer";
  id: string;
  club: OrderBookClubSummary | null;
  fee_amount: number | null;
  wage_weekly: number | null;
  status: string;
  is_countered: boolean;
  is_active: boolean;
  last_action_at: string;
}

export interface OrderBookTier {
  label: string;
  count: number;
  includes_yours: boolean;
}

export interface OrderBook {
  sale_id: string;
  role: "seller" | "buyer";
  active_count: number;
  // seller fields
  entries: OrderBookEntry[];
  summary: string;
  // buyer fields
  tiers: OrderBookTier[];
  your_rank: number | null;
  is_leading: boolean;
  your_entry: OrderBookEntry | null;
}

// ── AI admin ──────────────────────────────────────────────────────────────────

export interface AIUsageStats {
  total_requests: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_usd: number;
  by_endpoint: Record<string, { requests: number; cost_usd: number }>;
  note: string;
}

export interface PromptInfo {
  key: string;
  content: string;
  is_overridden: boolean;
  default_content: string;
}

// ── AI ────────────────────────────────────────────────────────────────────────

export interface RecommendedProfile {
  position: string;
  age_range: string;
  priority: "high" | "medium" | "low";
  reason: string;
}

export interface SquadAnalysisResponse {
  summary: string;
  positional_gaps: string[];
  age_risks: string[];
  contract_risks: string[];
  recommended_profiles: RecommendedProfile[];
  cached: boolean;
}

export interface PlayerFitResponse {
  fit_score: number;
  summary: string;
  strengths: string[];
  concerns: string[];
  cached: boolean;
}

export interface PlayerRecommendation {
  player_id: string;
  sale_id: string | null;
  name: string;
  position: string | null;
  fit_score: number;
  reason: string;
}

export interface MarketRecommendationsResponse {
  recommendations: PlayerRecommendation[];
  total_candidates: number;
  cached: boolean;
}

export interface ShortlistPlayerAssessment {
  player_id: string;
  name: string;
  fit_priority: "high" | "medium" | "low";
  addresses_gap: boolean;
  reason: string;
}

export interface ShortlistReviewResponse {
  summary: string;
  overall_verdict: "strong" | "adequate" | "weak";
  player_assessments: ShortlistPlayerAssessment[];
  top_picks: string[];
  missing_positions: string[];
  cached: boolean;
}

export interface NLParsedFilters {
  position: string | null;
  min_age: number | null;
  max_age: number | null;
  min_form_score: number | null;
  nationalities: string[] | null;
  min_height_cm: number | null;
  open_to_offers: boolean | null;
  interpreted_as: string;
}

export interface NLPlayerSearchResult {
  player_id: string;
  name: string;
  age: number | null;
  position: string | null;
  nationality: string | null;
  current_club: string | null;
  form_score: number | null;
  open_to_offers: boolean;
}

export interface NLSearchResponse {
  players: NLPlayerSearchResult[];
  filters: NLParsedFilters;
  total: number;
}
