"""How an anonymous buyer is named (docs/feature_spec/mobile-notifications §3.1).

A buyer who approaches anonymously stays hidden from the seller, and from
every other club, until the offer is accepted. The buyer always sees itself.
One rule, used wherever a buyer is named to someone else: the order book,
the assistant's facts, and the wording of notifications and pushes.
"""
import uuid


def buyer_is_masked(offer, viewer_club_id: uuid.UUID | str | None) -> bool:
    """True while `offer`'s buyer must stay hidden from `viewer_club_id`."""
    from app.offers.models import OfferStatus

    if not offer.is_anonymous or offer.status == OfferStatus.ACCEPTED:
        return False
    return viewer_club_id is None or str(viewer_club_id) != str(offer.from_club_id)


def masked_name(club, *, capitalise: bool = True) -> str:
    """What a hidden buyer is called: "A Premier League club", or "An
    undisclosed club" when the club has no domestic league to show."""
    league = getattr(club, "masking_league", None) if club is not None else None
    name = f"a {league} club" if league else "an undisclosed club"
    return name[0].upper() + name[1:] if capitalise else name


def buyer_name(offer, buyer_club, viewer_club_id, *, capitalise: bool = True) -> str:
    """The buyer as `viewer_club_id` may see it: its name, or the masked one."""
    if buyer_is_masked(offer, viewer_club_id):
        return masked_name(buyer_club, capitalise=capitalise)
    return buyer_club.name if buyer_club is not None else masked_name(None, capitalise=capitalise)
