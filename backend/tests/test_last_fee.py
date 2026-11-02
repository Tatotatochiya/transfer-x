"""A player's last transfer fee (app/players/last_fee.py)."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


def test_fees_in_every_shape_api_football_sends():
    from app.players.last_fee import fee_gbp

    assert round(fee_gbp("€ 116.6M")) == round(116_600_000 / 1.17)
    assert fee_gbp("&pound; 40M") == 40_000_000
    assert fee_gbp("£40M") == 40_000_000
    assert round(fee_gbp("$ 13.3M")) == 10_000_000
    assert round(fee_gbp("500K")) == round(500_000 / 1.17)  # no sign: euros
    assert fee_gbp("Free") is None and fee_gbp("Loan") is None and fee_gbp(None) is None and fee_gbp("N/A") is None


async def _player(db, name="Last Fee Larry"):
    from app.players.models import Player, PlayerStatus

    p = Player(name=name, position="MID", status=PlayerStatus.EXTERNAL, team_name="Arsenal")
    db.add(p)
    await db.commit()
    return p


def _move(p, day, fee, kind="Transfer", out="West Ham", to="Arsenal"):
    from app.players.models import PlayerTransfer

    return PlayerTransfer(player_id=p.id, vendor="api-football", transfer_date=day, transfer_type=kind,
                          fee_display=fee, team_out_name=out, team_in_name=to)


async def test_the_newest_paid_move_wins_and_loans_and_free_moves_dont_count(db):
    from app.players.last_fee import last_transfer_fees

    p = await _player(db)
    db.add_all([_move(p, date(2019, 7, 1), "€ 40M", out="Chelsea", to="West Ham"),
                _move(p, date(2023, 7, 15), "€ 116.6M"),
                _move(p, date(2024, 1, 10), None, kind="Loan", to="Somewhere"),
                _move(p, date(2025, 8, 1), "Free", to="Elsewhere")])
    await db.commit()
    got = (await last_transfer_fees(db, [p.id]))[p.id]
    assert (got["date"], got["from"], got["to"], got["fee_display"]) == ("2023-07-15", "West Ham", "Arsenal", "€ 116.6M")
    assert got["fee_gbp"] == round(116_600_000 / 1.17) and got["source"] == "API-Football"
    assert await last_transfer_fees(db, [uuid.uuid4()]) == {}


async def test_a_later_transferx_deal_wins_unless_its_a_test(client: AsyncClient, db):
    from app.deals.models import Deal, DealStage, DealStatus
    from app.players.last_fee import last_transfer_fees
    from tests.test_deals import _get_club_id

    buyer = await _register(client, "fee_buyer@fee-example.com", club_name="Fee Buyers")
    seller = await _register(client, "fee_seller@fee-example.com", club_name="Fee Sellers")
    p = await _player(db)
    db.add(_move(p, date(2023, 7, 15), "€ 116.6M"))
    deal = Deal(buyer_club_id=uuid.UUID(await _get_club_id(client, _auth_headers(buyer))),
                seller_club_id=uuid.UUID(await _get_club_id(client, _auth_headers(seller))),
                player_id=p.id, agreed_fee=Decimal(45_000_000), status=DealStatus.COMPLETED, stage=DealStage.COMPLETED,
                completed_at=datetime(2026, 9, 30, 12, tzinfo=timezone.utc))
    db.add(deal)
    await db.commit()
    got = (await last_transfer_fees(db, [p.id]))[p.id]
    assert (got["fee_gbp"], got["source"], got["from"], got["to"]) == (45_000_000, "TransferX", "Fee Sellers", "Fee Buyers")
    deal.is_test = True
    await db.commit()
    assert (await last_transfer_fees(db, [p.id]))[p.id]["source"] == "API-Football"


async def test_the_player_page_and_the_value_api_show_it(client: AsyncClient, db):
    from app.valuation.models import PlayerValuation, ValuationConfidence

    viewer = await _register(client, "fee_viewer@fee-example.com", club_name="Fee Viewers")
    p = await _player(db)
    db.add(_move(p, date(2023, 7, 15), "€ 116.6M"))
    db.add(PlayerValuation(player_id=p.id, fair_value=Decimal(60_000_000), fair_value_low=Decimal(50_000_000),
                           fair_value_high=Decimal(70_000_000), performance_score=Decimal("70"),
                           confidence=list(ValuationConfidence)[0], model_version="test", league_tier=1,
                           age_factor=Decimal("1")))
    await db.commit()
    h = _auth_headers(viewer)
    ledger = (await client.get(f"/players/market/{p.id}/ledger", headers=h)).json()
    assert ledger["last_transfer"]["to"] == "Arsenal"
    one = (await client.get(f"/valuation/players/{p.id}", headers=h)).json()
    assert one["last_transfer"]["from"] == "West Ham" and one["last_transfer"]["date"] == "2023-07-15"
    batch = (await client.get(f"/valuation/players?ids={p.id}", headers=h)).json()
    assert batch["valuations"][str(p.id)]["last_transfer"]["fee_display"] == "€ 116.6M"
