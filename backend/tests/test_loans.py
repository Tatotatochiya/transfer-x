"""Loan execution — feature_spec/loan-transfers.md phase 2.

Phase 1's tests cover the offer side (types, validation, reservation). These
cover what happens when a loan deal actually completes: the registration moves,
ownership does not, and the money lands on the right side of both books.
"""
import uuid as uuid_mod
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register


@pytest_asyncio.fixture
async def parent(client: AsyncClient) -> dict:
    return await _register(client, "parent_loan@test.com", club_name="Parent FC")


@pytest_asyncio.fixture
async def loanee(client: AsyncClient) -> dict:
    return await _register(client, "loanee_loan@test.com", club_name="Loanee FC")


@pytest_asyncio.fixture
async def outsider(client: AsyncClient) -> dict:
    return await _register(client, "outsider_loan@test.com", club_name="Outsider FC")


async def _budgets(db, transfer=Decimal("50000000"), wage=Decimal("500000")):
    from app.clubs.models import ClubFinance

    for f in (await db.execute(select(ClubFinance))).scalars():
        f.transfer_budget_total = transfer
        f.wage_budget_total_weekly = wage
    await db.commit()


async def _club_id(client: AsyncClient, headers: dict) -> str:
    return (await client.get("/clubs/me", headers=headers)).json()["id"]


async def _player_with_contract(
    client: AsyncClient, db, headers: dict, club_id: str,
    *, wage=Decimal("90000"), end=date(2029, 6, 30), name="Loan Player",
) -> dict:
    from app.players.models import Contract, Player

    resp = await client.post(
        "/players", json={"name": name, "position": "MID"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    player = resp.json()
    db.add(Contract(
        player_id=uuid_mod.UUID(player["id"]),
        club_id=uuid_mod.UUID(club_id),
        end_date=end,
        wage_weekly=wage,
        is_active=True,
    ))
    # Inserting a Contract directly does not touch ClubFinance — in the real
    # app the wage lands in wage_reserved_weekly when the signing deal
    # completes. Model that, or the club looks like it is paying nobody and
    # the loan's relief has nothing to come out of.
    fin = await _finance(db, club_id)
    fin.wage_reserved_weekly += wage
    await db.commit()
    # normalize so current_club_id / status reflect the contract
    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    from app.players import service as players_service

    await players_service.normalize_player_status(db, row)
    await db.commit()
    return player


async def _finance(db, club_id: str):
    from app.clubs.models import ClubFinance

    return (
        await db.execute(
            select(ClubFinance).where(ClubFinance.club_id == uuid_mod.UUID(club_id))
        )
    ).scalar_one()


async def _run_loan_to_completion(
    client: AsyncClient, db, parent: dict, loanee: dict,
    *, loan_end=date(2027, 5, 31), split=0.6, fee=2_000_000, wage=Decimal("90000"),
):
    """Offer -> accept -> force-complete as staff. Returns (player, deal_id, loan)."""
    from app.auth.models import User
    from app.deals import service as deals_service
    from app.deals.models import Deal
    from app.loans.models import PlayerLoan

    p_headers, l_headers = _auth_headers(parent), _auth_headers(loanee)
    await _budgets(db)
    parent_club = await _club_id(client, p_headers)
    player = await _player_with_contract(client, db, p_headers, parent_club, wage=wage)

    offer = (await client.post(
        "/offers",
        json={
            "player_id": player["id"], "to_club_id": parent_club,
            "deal_type": "LOAN",
            "loan_start": str(date(2026, 9, 1)), "loan_end": str(loan_end),
            "loan_fee": fee, "wage_weekly": float(wage), "wage_split_pct": split,
        },
        headers=l_headers,
    )).json()
    assert "id" in offer, offer

    deal_id = (await client.post(
        f"/offers/{offer['id']}/accept", headers=p_headers
    )).json()["id"]

    deal = (
        await db.execute(select(Deal).where(Deal.id == uuid_mod.UUID(deal_id)))
    ).scalar_one()
    await deals_service._complete_deal(db, deal)
    await db.commit()

    loan = (
        await db.execute(
            select(PlayerLoan).where(PlayerLoan.deal_id == uuid_mod.UUID(deal_id))
        )
    ).scalar_one()
    return player, deal_id, loan


@pytest.mark.asyncio
async def test_completing_a_loan_moves_registration_not_ownership(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    from app.players import service as players_service
    from app.players.models import Player

    player, _, loan = await _run_loan_to_completion(client, db, parent, loanee)
    p_headers, l_headers = _auth_headers(parent), _auth_headers(loanee)
    parent_club = await _club_id(client, p_headers)
    loanee_club = await _club_id(client, l_headers)

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)

    # The loanee holds the registration...
    assert str(row.current_club_id) == loanee_club
    # ...but the parent still owns him. Without this the loanee could sell him.
    owner = await players_service.get_owning_club_id(db, row)
    assert str(owner) == parent_club

    assert loan.status.value == "ACTIVE"
    assert str(loan.parent_club_id) == parent_club
    assert str(loan.loanee_club_id) == loanee_club
    assert loan.parent_contract_id is not None  # the restore pointer


@pytest.mark.asyncio
async def test_loan_leaves_exactly_one_active_contract(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """The invariant the whole design is built around: normalize_player_status
    uses scalar_one_or_none(), so two active contracts raise, not misbehave."""
    from app.players import service as players_service
    from app.players.models import Contract, Player

    player, _, _ = await _run_loan_to_completion(client, db, parent, loanee)

    active = (
        await db.execute(
            select(Contract).where(
                Contract.player_id == uuid_mod.UUID(player["id"]),
                Contract.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    assert len(active) == 1

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await players_service.normalize_player_status(db, row)  # must not raise


@pytest.mark.asyncio
async def test_loan_splits_the_wage_across_both_books(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """60% of a 90k wage: the loanee carries 54k, the parent is relieved of
    exactly that and keeps the remaining 36k."""
    p_headers, l_headers = _auth_headers(parent), _auth_headers(loanee)
    await _budgets(db)
    parent_club_pre = await _club_id(client, p_headers)
    parent_fin = await _finance(db, parent_club_pre)
    await db.refresh(parent_fin)

    player, _, loan = await _run_loan_to_completion(client, db, parent, loanee)
    loanee_club = await _club_id(client, l_headers)

    lf = await _finance(db, loanee_club)
    pf = await _finance(db, parent_club_pre)
    await db.refresh(lf)
    await db.refresh(pf)

    assert loan.loanee_wage_share == Decimal("54000.00")
    assert lf.wage_reserved_weekly == Decimal("54000.00")
    assert lf.transfer_spent == Decimal("2000000.00")
    # The parent banks the loan fee and keeps paying its 36k share.
    assert pf.transfer_budget_total == Decimal("52000000.00")
    assert pf.wage_reserved_weekly == Decimal("36000.00")


@pytest.mark.asyncio
async def test_loanee_cannot_sell_a_player_they_only_borrowed(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    player, _, _ = await _run_loan_to_completion(client, db, parent, loanee)
    l_headers = _auth_headers(loanee)

    resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "FIXED_PRICE", "asking_price": 20_000_000},
        headers=l_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "not registered to your club" in resp.text


@pytest.mark.asyncio
async def test_parent_can_still_sell_a_player_who_is_out_on_loan(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """D6's premise: blocking would make a loaned player unsellable for a year."""
    player, _, _ = await _run_loan_to_completion(client, db, parent, loanee)
    p_headers = _auth_headers(parent)

    resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "FIXED_PRICE", "asking_price": 20_000_000},
        headers=p_headers,
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_returning_a_loan_restores_the_parent_contract_and_wage(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    from app.loans import service as loans_service
    from app.loans.models import LoanEndReason
    from app.players.models import Contract, Player

    player, _, loan = await _run_loan_to_completion(client, db, parent, loanee)
    p_headers, l_headers = _auth_headers(parent), _auth_headers(loanee)
    parent_club = await _club_id(client, p_headers)
    loanee_club = await _club_id(client, l_headers)

    await loans_service.end_loan(db, loan, reason=LoanEndReason.EXPIRED)
    await db.commit()

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert str(row.current_club_id) == parent_club
    assert row.status.value == "CONTRACTED"

    active = (
        await db.execute(
            select(Contract).where(
                Contract.player_id == uuid_mod.UUID(player["id"]),
                Contract.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    assert len(active) == 1
    assert str(active[0].club_id) == parent_club  # the restored original, not a new one
    assert str(active[0].id) == str(loan.parent_contract_id)

    lf = await _finance(db, loanee_club)
    pf = await _finance(db, parent_club)
    await db.refresh(lf)
    await db.refresh(pf)
    assert lf.wage_reserved_weekly == Decimal("0.00")
    assert pf.wage_reserved_weekly == Decimal("90000.00")  # back to the full wage
    assert loan.status.value == "COMPLETED"


@pytest.mark.asyncio
async def test_return_makes_a_free_agent_when_the_parent_contract_expired(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """The one path in this feature that can turn a squad player into a free
    agent, which is exactly why offer validation refuses a loan that outlasts
    the parent contract. Reachable only if the contract is changed mid-loan."""
    from app.loans import service as loans_service
    from app.loans.models import LoanEndReason
    from app.players.models import Contract, Player

    player, _, loan = await _run_loan_to_completion(client, db, parent, loanee)

    # Expire the parent's suspended contract behind the loan's back.
    parent_contract = (
        await db.execute(select(Contract).where(Contract.id == loan.parent_contract_id))
    ).scalar_one()
    parent_contract.end_date = date.today() - timedelta(days=1)
    await db.commit()

    await loans_service.end_loan(db, loan, reason=LoanEndReason.EXPIRED)
    await db.commit()

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert row.current_club_id is None
    assert row.status.value in ("FREE_AGENT", "EXTERNAL")

    active = (
        await db.execute(
            select(Contract).where(
                Contract.player_id == uuid_mod.UUID(player["id"]),
                Contract.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    assert active == []


@pytest.mark.asyncio
async def test_a_loan_cannot_be_ended_twice(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    from app.loans import service as loans_service
    from app.loans.models import LoanEndReason

    _, _, loan = await _run_loan_to_completion(client, db, parent, loanee)
    await loans_service.end_loan(db, loan, reason=LoanEndReason.EXPIRED)
    await db.commit()

    with pytest.raises(ValueError, match="already"):
        await loans_service.end_loan(db, loan, reason=LoanEndReason.EXPIRED)


@pytest.mark.asyncio
async def test_selling_a_loaned_player_terminates_the_loan(
    client: AsyncClient, parent: dict, loanee: dict, outsider: dict, db
):
    """D6. The buyer gets the player, the loan ends as CONVERTED/PARENT_SOLD,
    and the loanee stops paying — with still exactly one active contract."""
    from app.deals import service as deals_service
    from app.deals.models import Deal
    from app.loans.models import PlayerLoan
    from app.players.models import Contract, Player

    player, _, loan = await _run_loan_to_completion(client, db, parent, loanee)
    p_headers, l_headers, o_headers = (
        _auth_headers(parent), _auth_headers(loanee), _auth_headers(outsider)
    )
    parent_club = await _club_id(client, p_headers)
    loanee_club = await _club_id(client, l_headers)
    outsider_club = await _club_id(client, o_headers)

    # The outsider buys him from the parent while he is away on loan.
    offer = (await client.post(
        "/offers",
        json={
            "player_id": player["id"], "to_club_id": parent_club,
            "fee_amount": 12_000_000, "wage_weekly": 70_000,
        },
        headers=o_headers,
    )).json()
    assert "id" in offer, offer
    deal_id = (await client.post(
        f"/offers/{offer['id']}/accept", headers=p_headers
    )).json()["id"]

    deal = (
        await db.execute(select(Deal).where(Deal.id == uuid_mod.UUID(deal_id)))
    ).scalar_one()
    await deals_service._complete_deal(db, deal)
    await db.commit()

    refreshed = (
        await db.execute(select(PlayerLoan).where(PlayerLoan.id == loan.id))
    ).scalar_one()
    await db.refresh(refreshed)
    assert refreshed.status.value == "CONVERTED"
    assert refreshed.end_reason == "PARENT_SOLD"

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert str(row.current_club_id) == outsider_club

    active = (
        await db.execute(
            select(Contract).where(
                Contract.player_id == uuid_mod.UUID(player["id"]),
                Contract.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    assert len(active) == 1
    assert str(active[0].club_id) == outsider_club

    # The loanee stops paying the moment the sale completes.
    lf = await _finance(db, loanee_club)
    await db.refresh(lf)
    assert lf.wage_reserved_weekly == Decimal("0.00")

    # And the parent is no longer carrying their retained share either.
    pf = await _finance(db, parent_club)
    await db.refresh(pf)
    assert pf.wage_reserved_weekly == Decimal("0.00")


@pytest.mark.asyncio
async def test_a_loan_does_not_trigger_a_previous_owners_sell_on(
    client: AsyncClient, parent: dict, loanee: dict, outsider: dict, db
):
    """A loan is not a resale. The permanent path pays a prior sell-on clause
    when a fee changes hands; doing that on a loan would be a real mispayment."""
    from app.deals.models import Deal, DealStatus, DealType
    from app.notifications.models import Notification, NotificationType

    p_headers, o_headers = _auth_headers(parent), _auth_headers(outsider)
    await _budgets(db)
    parent_club = await _club_id(client, p_headers)
    outsider_club = await _club_id(client, o_headers)

    player, _, _ = await _run_loan_to_completion(client, db, parent, loanee)

    # A completed prior sale, with the outsider holding a 20% sell-on.
    db.add(Deal(
        buyer_club_id=uuid_mod.UUID(parent_club),
        seller_club_id=uuid_mod.UUID(outsider_club),
        player_id=uuid_mod.UUID(player["id"]),
        agreed_fee=Decimal("5000000"),
        status=DealStatus.COMPLETED,
        deal_type=DealType.PERMANENT,
        sell_on_pct=Decimal("0.2000"),
        completed_at=None,
    ))
    await db.commit()

    sell_on_notes = (
        await db.execute(
            select(Notification).where(
                Notification.type == NotificationType.DEAL_SELL_ON,
                Notification.related_player_id == uuid_mod.UUID(player["id"]),
            )
        )
    ).scalars().all()
    assert sell_on_notes == []
