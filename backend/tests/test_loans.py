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
    recall_allowed=False, option_to_buy=None, obligation=False,
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
            "recall_allowed": recall_allowed,
            **({"option_to_buy": option_to_buy} if option_to_buy else {}),
            **({"obligation_to_buy": True} if obligation else {}),
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


# ── Phase 3: endpoints, recall, expiry job ───────────────────────────────────


@pytest.mark.asyncio
async def test_list_my_loans_shows_direction_for_each_side(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """The same row means different things to the two clubs — one is missing a
    player, the other has borrowed one — so the server says which."""
    player, _, _ = await _run_loan_to_completion(client, db, parent, loanee)

    out = (await client.get("/clubs/me/loans", headers=_auth_headers(parent))).json()
    assert len(out) == 1
    assert out[0]["direction"] == "out"
    assert out[0]["player"]["name"] == player["name"]

    inn = (await client.get("/clubs/me/loans", headers=_auth_headers(loanee))).json()
    assert len(inn) == 1
    assert inn[0]["direction"] == "in"


@pytest.mark.asyncio
async def test_list_my_loans_filters_by_direction(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    await _run_loan_to_completion(client, db, parent, loanee)
    p = _auth_headers(parent)
    assert len((await client.get("/clubs/me/loans?direction=out", headers=p)).json()) == 1
    assert len((await client.get("/clubs/me/loans?direction=in", headers=p)).json()) == 0


@pytest.mark.asyncio
async def test_a_third_club_cannot_see_the_loan(
    client: AsyncClient, parent: dict, loanee: dict, outsider: dict, db
):
    """404 rather than 403: whether a loan exists is not a third club's to learn."""
    _, _, loan = await _run_loan_to_completion(client, db, parent, loanee)

    resp = await client.get(f"/loans/{loan.id}", headers=_auth_headers(outsider))
    assert resp.status_code == 404
    assert (await client.get("/clubs/me/loans", headers=_auth_headers(outsider))).json() == []


@pytest.mark.asyncio
async def test_recall_returns_the_player_to_the_parent(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    from app.players.models import Contract, Player

    player, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, recall_allowed=True
    )
    parent_club = await _club_id(client, _auth_headers(parent))

    resp = await client.post(f"/loans/{loan.id}/recall", headers=_auth_headers(parent))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "RECALLED"

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert str(row.current_club_id) == parent_club

    active = (
        await db.execute(
            select(Contract).where(
                Contract.player_id == uuid_mod.UUID(player["id"]),
                Contract.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    assert len(active) == 1
    assert str(active[0].club_id) == parent_club


@pytest.mark.asyncio
async def test_the_loanee_cannot_recall(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    _, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, recall_allowed=True
    )
    resp = await client.post(f"/loans/{loan.id}/recall", headers=_auth_headers(loanee))
    assert resp.status_code == 403, resp.text
    assert "parent club" in resp.text


@pytest.mark.asyncio
async def test_recall_refused_when_the_terms_did_not_allow_it(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    _, _, loan = await _run_loan_to_completion(client, db, parent, loanee)  # default False
    resp = await client.post(f"/loans/{loan.id}/recall", headers=_auth_headers(parent))
    assert resp.status_code == 400, resp.text
    assert "without a recall option" in resp.text


@pytest.mark.asyncio
async def test_expiry_job_returns_a_loan_that_has_run_its_term(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    from app.loans import service as loans_service
    from app.loans.models import PlayerLoan
    from app.players.models import Player

    player, _, loan = await _run_loan_to_completion(client, db, parent, loanee)
    parent_club = await _club_id(client, _auth_headers(parent))
    loanee_club = await _club_id(client, _auth_headers(loanee))

    loan.end_date = date.today() - timedelta(days=1)
    await db.commit()

    result = await loans_service.process_due_loans(db)
    await db.commit()
    assert result["returned"] == 1

    refreshed = (
        await db.execute(select(PlayerLoan).where(PlayerLoan.id == loan.id))
    ).scalar_one()
    await db.refresh(refreshed)
    assert refreshed.status.value == "COMPLETED"
    assert refreshed.end_reason == "EXPIRED"

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert str(row.current_club_id) == parent_club

    lf = await _finance(db, loanee_club)
    pf = await _finance(db, parent_club)
    await db.refresh(lf)
    await db.refresh(pf)
    assert lf.wage_reserved_weekly == Decimal("0.00")
    assert pf.wage_reserved_weekly == Decimal("90000.00")


@pytest.mark.asyncio
async def test_expiry_job_leaves_a_loan_that_is_still_running(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    from app.loans import service as loans_service

    _, _, loan = await _run_loan_to_completion(client, db, parent, loanee)
    result = await loans_service.process_due_loans(db)
    assert result["returned"] == 0
    assert loan.status.value == "ACTIVE"


@pytest.mark.asyncio
async def test_ending_soon_warns_once_not_every_day(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """Without the guard the job re-warns both clubs daily for two weeks."""
    from app.loans import service as loans_service
    from app.notifications.models import Notification, NotificationType

    _, _, loan = await _run_loan_to_completion(client, db, parent, loanee)
    loan.end_date = date.today() + timedelta(days=7)
    await db.commit()

    first = await loans_service.process_due_loans(db)
    await db.commit()
    assert first["ending_soon_warned"] == 1

    second = await loans_service.process_due_loans(db)
    await db.commit()
    assert second["ending_soon_warned"] == 0

    notes = (
        await db.execute(
            select(Notification).where(
                Notification.type == NotificationType.LOAN_ENDING_SOON
            )
        )
    ).scalars().all()
    assert len(notes) == 2  # one per club, once


@pytest.mark.asyncio
async def test_both_clubs_are_told_when_a_loan_starts(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    from app.notifications.models import Notification, NotificationType

    await _run_loan_to_completion(client, db, parent, loanee)
    notes = (
        await db.execute(
            select(Notification).where(Notification.type == NotificationType.LOAN_STARTED)
        )
    ).scalars().all()
    assert len(notes) == 2


# ── Phase 4: option and obligation to buy ────────────────────────────────────


@pytest.mark.asyncio
async def test_exercising_an_option_creates_a_permanent_deal_and_leaves_the_loan_running(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """The loan deliberately stays ACTIVE while the purchase runs. Ending it
    here would deactivate his registration and leave him with no active
    contract at all for however many days the deal takes."""
    from app.deals.models import Deal, DealStatus, DealType
    from app.loans.models import PlayerLoan
    from app.players.models import Player

    player, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, option_to_buy=18_000_000
    )
    loanee_club = await _club_id(client, _auth_headers(loanee))
    parent_club = await _club_id(client, _auth_headers(parent))

    resp = await client.post(
        f"/loans/{loan.id}/exercise-option", headers=_auth_headers(loanee)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ACTIVE"
    assert body["conversion_deal_id"] is not None

    deal = (
        await db.execute(
            select(Deal).where(Deal.id == uuid_mod.UUID(body["conversion_deal_id"]))
        )
    ).scalar_one()
    assert deal.deal_type == DealType.PERMANENT
    assert deal.status == DealStatus.IN_PROGRESS
    assert str(deal.buyer_club_id) == loanee_club
    assert str(deal.seller_club_id) == parent_club
    assert deal.agreed_fee == Decimal("18000000.00")

    # He is still registered at the loanee, under the loan, while it runs.
    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert str(row.current_club_id) == loanee_club


@pytest.mark.asyncio
async def test_completing_the_conversion_ends_the_loan_as_option_exercised(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """Not PARENT_SOLD: the buyer is the loanee, so this is them buying him,
    not the parent selling him to a third club."""
    from app.deals import service as deals_service
    from app.deals.models import Deal
    from app.loans.models import PlayerLoan
    from app.players.models import Contract, Player

    player, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, option_to_buy=18_000_000
    )
    loanee_club = await _club_id(client, _auth_headers(loanee))

    body = (await client.post(
        f"/loans/{loan.id}/exercise-option", headers=_auth_headers(loanee)
    )).json()
    deal = (
        await db.execute(
            select(Deal).where(Deal.id == uuid_mod.UUID(body["conversion_deal_id"]))
        )
    ).scalar_one()
    await deals_service._complete_deal(db, deal)
    await db.commit()

    refreshed = (
        await db.execute(select(PlayerLoan).where(PlayerLoan.id == loan.id))
    ).scalar_one()
    await db.refresh(refreshed)
    assert refreshed.status.value == "CONVERTED"
    assert refreshed.end_reason == "OPTION_EXERCISED"

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert str(row.current_club_id) == loanee_club

    active = (
        await db.execute(
            select(Contract).where(
                Contract.player_id == uuid_mod.UUID(player["id"]),
                Contract.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    assert len(active) == 1
    assert str(active[0].club_id) == loanee_club


@pytest.mark.asyncio
async def test_only_the_loanee_can_exercise_the_option(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    _, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, option_to_buy=18_000_000
    )
    resp = await client.post(
        f"/loans/{loan.id}/exercise-option", headers=_auth_headers(parent)
    )
    assert resp.status_code == 403, resp.text
    assert "on loan at" in resp.text


@pytest.mark.asyncio
async def test_no_option_means_nothing_to_exercise(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    _, _, loan = await _run_loan_to_completion(client, db, parent, loanee)  # no option
    resp = await client.post(
        f"/loans/{loan.id}/exercise-option", headers=_auth_headers(loanee)
    )
    assert resp.status_code == 400, resp.text
    assert "without an option to buy" in resp.text


@pytest.mark.asyncio
async def test_an_option_cannot_be_exercised_twice(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    _, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, option_to_buy=18_000_000
    )
    first = await client.post(
        f"/loans/{loan.id}/exercise-option", headers=_auth_headers(loanee)
    )
    assert first.status_code == 200, first.text
    second = await client.post(
        f"/loans/{loan.id}/exercise-option", headers=_auth_headers(loanee)
    )
    assert second.status_code == 400, second.text
    assert "already being made permanent" in second.text


@pytest.mark.asyncio
async def test_an_obligation_converts_at_expiry_instead_of_returning_him(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """D7. The clubs already agreed he would be bought, so sending him home and
    asking them to redo it as a fresh transfer would contradict the terms."""
    from app.deals.models import Deal, DealStatus, DealType
    from app.loans import service as loans_service
    from app.loans.models import PlayerLoan
    from app.players.models import Player

    player, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, option_to_buy=18_000_000, obligation=True
    )
    loanee_club = await _club_id(client, _auth_headers(loanee))

    loan.end_date = date.today() - timedelta(days=1)
    await db.commit()

    result = await loans_service.process_due_loans(db)
    await db.commit()
    assert result["converted"] == 1
    assert result["returned"] == 0  # he did NOT go home

    refreshed = (
        await db.execute(select(PlayerLoan).where(PlayerLoan.id == loan.id))
    ).scalar_one()
    await db.refresh(refreshed)
    assert refreshed.status.value == "ACTIVE"  # ends when the deal completes
    assert refreshed.conversion_deal_id is not None

    deal = (
        await db.execute(select(Deal).where(Deal.id == refreshed.conversion_deal_id))
    ).scalar_one()
    assert deal.deal_type == DealType.PERMANENT
    assert deal.agreed_fee == Decimal("18000000.00")
    assert str(deal.buyer_club_id) == loanee_club

    # Still at the loanee while the purchase runs.
    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert str(row.current_club_id) == loanee_club


@pytest.mark.asyncio
async def test_the_expiry_job_does_not_start_a_second_conversion(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """Without conversion_deal_id the job would create a fresh deal for the
    same obligation on every daily run."""
    from app.deals.models import Deal
    from app.loans import service as loans_service

    _, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, option_to_buy=18_000_000, obligation=True
    )
    loan.end_date = date.today() - timedelta(days=1)
    await db.commit()

    first = await loans_service.process_due_loans(db)
    await db.commit()
    second = await loans_service.process_due_loans(db)
    await db.commit()
    assert first["converted"] == 1
    assert second["converted"] == 0

    deals = (
        await db.execute(
            select(Deal).where(Deal.player_id == uuid_mod.UUID(str(loan.player_id)))
        )
    ).scalars().all()
    # the original LOAN deal plus exactly one conversion
    assert len(deals) == 2


@pytest.mark.asyncio
async def test_an_option_without_an_obligation_is_never_automatic(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    """An option is a right, not a commitment: at expiry he goes home unless
    the loanee actually took it."""
    from app.loans import service as loans_service
    from app.loans.models import PlayerLoan
    from app.players.models import Player

    player, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, option_to_buy=18_000_000  # option, no obligation
    )
    parent_club = await _club_id(client, _auth_headers(parent))
    loan.end_date = date.today() - timedelta(days=1)
    await db.commit()

    result = await loans_service.process_due_loans(db)
    await db.commit()
    assert result["converted"] == 0
    assert result["returned"] == 1

    refreshed = (
        await db.execute(select(PlayerLoan).where(PlayerLoan.id == loan.id))
    ).scalar_one()
    await db.refresh(refreshed)
    assert refreshed.status.value == "COMPLETED"
    assert refreshed.conversion_deal_id is None

    row = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(row)
    assert str(row.current_club_id) == parent_club


@pytest.mark.asyncio
async def test_both_clubs_are_told_a_loan_is_becoming_permanent(
    client: AsyncClient, parent: dict, loanee: dict, db
):
    from app.notifications.models import Notification, NotificationType

    _, _, loan = await _run_loan_to_completion(
        client, db, parent, loanee, option_to_buy=18_000_000
    )
    await client.post(f"/loans/{loan.id}/exercise-option", headers=_auth_headers(loanee))

    notes = (
        await db.execute(
            select(Notification).where(
                Notification.type == NotificationType.LOAN_CONVERTED
            )
        )
    ).scalars().all()
    assert len(notes) == 2
