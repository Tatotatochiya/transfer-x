"""Which notification types reach a phone, and how (mobile notifications §2).

Every type is in exactly one tier. The map lives in code rather than the
database so it can change without a migration; a test fails if a new
`NotificationType` is added without a tier.

- YOUR_MOVE: pushed straight away with sound, and the only tier that counts
  towards the app badge and may break through quiet hours.
- HEADS_UP: pushed straight away, silent.
- FYI: never pushed. It stays in the in-app list and is counted in the
  morning summary.
"""
import enum

from app.notifications.models import NotificationType as T


class Tier(str, enum.Enum):
    YOUR_MOVE = "YOUR_MOVE"
    HEADS_UP = "HEADS_UP"
    FYI = "FYI"


_YOUR_MOVE = {T.OFFER_RECEIVED, T.OFFER_COUNTERED, T.APPROVAL_REQUESTED, T.DEAL_PERSONAL_TERMS_SENT}

_HEADS_UP = {
    T.OUTBID, T.OFFER_EXPIRING, T.AUCTION_ENDING, T.AUCTION_BID_RECEIVED, T.OFFER_MESSAGE,
    T.NEGOTIATION_MESSAGE, T.ENQUIRY_RECEIVED, T.ENQUIRY_REPLIED, T.OFFER_ACCEPTED, T.OFFER_REJECTED,
    T.AUCTION_BID_ACCEPTED, T.DEAL_COLLAPSED, T.DEAL_SLA_BREACHED, T.SALE_REOPENED, T.INSTALMENT_DUE,
    T.RELEASE_CLAUSE_TRIGGERED, T.LOAN_RECALLED,
}

# DAILY_DIGEST is a preference rather than a notification anyone receives;
# it switches the digest email and the morning summary push (§6.2).
_FYI = {
    T.OFFER_WITHDRAWN, T.DEAL_COMPLETED, T.DEAL_SELL_ON, T.DEAL_AGENT_INVITED, T.DEAL_PAPERWORK,
    T.DEAL_CLAUSE_TRIGGERED, T.PERSONAL_TERMS_DECISION, T.PLAYER_AVAILABLE, T.SYSTEM_BROADCAST,
    T.VERIFICATION_APPROVED, T.VERIFICATION_REJECTED, T.REPRESENTATION_STARTED, T.REPRESENTATION_REVOKED,
    T.REPRESENTATION_EXPIRED, T.CLIENT_ALERT, T.STAFF_INVITATION, T.APPROVAL_DECIDED, T.LOAN_STARTED,
    T.LOAN_ENDING_SOON, T.LOAN_ENDED, T.LOAN_CONVERTED, T.DAILY_DIGEST,
}

TIERS: dict[T, Tier] = {
    **{t: Tier.YOUR_MOVE for t in _YOUR_MOVE},
    **{t: Tier.HEADS_UP for t in _HEADS_UP},
    **{t: Tier.FYI for t in _FYI},
}


def tier_of(type_: T) -> Tier:
    return TIERS[type_]


# What the lock screen says when the user hides amounts (review decision 1).
# No figures, no club names, no message text: only what kind of thing
# happened. The details are one tap away, behind the phone's lock.
HIDDEN_TITLES: dict[T, str] = {
    T.OFFER_RECEIVED: "New offer received",
    T.OFFER_COUNTERED: "Your offer was countered",
    T.APPROVAL_REQUESTED: "An approval needs you",
    T.DEAL_PERSONAL_TERMS_SENT: "Personal terms to review",
    T.OUTBID: "You've been outbid",
    T.OFFER_EXPIRING: "An offer is expiring soon",
    T.AUCTION_ENDING: "An auction is ending soon",
    T.AUCTION_BID_RECEIVED: "New bid on your auction",
    T.OFFER_MESSAGE: "New message on an offer",
    T.NEGOTIATION_MESSAGE: "New message in a negotiation",
    T.ENQUIRY_RECEIVED: "New enquiry",
    T.ENQUIRY_REPLIED: "Reply to your enquiry",
    T.OFFER_ACCEPTED: "Your offer was accepted",
    T.OFFER_REJECTED: "Your offer was turned down",
    T.AUCTION_BID_ACCEPTED: "Your bid was accepted",
    T.DEAL_COLLAPSED: "A deal has collapsed",
    T.DEAL_SLA_BREACHED: "A deal is overdue",
    T.SALE_REOPENED: "A sale has reopened",
    T.INSTALMENT_DUE: "An instalment is due",
    T.RELEASE_CLAUSE_TRIGGERED: "A release clause was triggered",
    T.LOAN_RECALLED: "A loan was recalled",
}
HIDDEN_BODY = "Open TransferX to see the details."


def hidden_title(type_: T) -> str:
    return HIDDEN_TITLES.get(type_, "New notification")
