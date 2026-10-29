"""Demo mode routes (app/demo): a tester's run, playing a house club, and the staff side."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.deps import get_current_superuser, get_current_user
from app.demo import service
from app.demo.models import DemoRun

router = APIRouter(tags=["demo"])


async def _own_run(db: AsyncSession, user: User) -> DemoRun:
    run = await service.active_run(db, user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You have no demo running.")
    return run


@router.get("/demo/run")
async def current_run(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The caller's active demo, or null; and whether they may start one."""
    return {"can_demo": service.can_demo(current_user),
            "run": await service.describe(db, await service.active_run(db, current_user.id))}


@router.post("/demo/run", status_code=status.HTTP_201_CREATED)
async def start_run(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start a demo: from now on, what you change (and what it sets off) can be reset."""
    try:
        run = await service.start(db, current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await db.commit()
    return await service.describe(db, run)


@router.post("/demo/run/reset")
async def reset_run(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Put back everything your demo changed."""
    run = await _own_run(db, current_user)
    report = await service.reset(db, run, by_user_id=current_user.id)
    await db.commit()
    return report


@router.post("/demo/run/keep")
async def keep_run(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """End your demo and keep what it changed."""
    run = await _own_run(db, current_user)
    await service.keep(db, run, by_user_id=current_user.id)
    await db.commit()
    return {"kept": True}


@router.get("/demo/house-clubs")
async def house_clubs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """The clubs TransferX plays, for a tester to deal with or play by hand."""
    from app.clubs.models import Club

    if not service.can_demo(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode isn't available to you.")
    clubs = (await db.execute(select(Club).where(Club.house_club.is_(True)).order_by(Club.name))).scalars().all()
    return [{"id": str(c.id), "name": c.name, "crest_url": c.crest_url, "personality": c.house_personality}
            for c in clubs]


@router.post("/demo/house-clubs/{club_id}/play-as")
async def play_as(
    club_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """A tab signed in as a house club, to play the other side of your demo
    by hand. Everything it does belongs to your demo and is reset with it."""
    from app.auth import service as auth_service
    from app.clubs.models import Club

    run = await _own_run(db, current_user)
    club = await db.get(Club, club_id)
    if club is None or not club.house_club:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a house club.")
    owner = await db.get(User, club.user_id)
    if owner is None or not owner.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This club's account is not active.")
    token, expires_at = auth_service.create_play_as_token(owner.id, owner.email, run_id=run.id,
                                                          tester_user_id=current_user.id)
    return {"access_token": token, "expires_at": expires_at.isoformat(), "club_name": club.name}


# ── Staff ────────────────────────────────────────────────────────────────────


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class HouseClubRequest(ReasonRequest):
    house_club: bool
    personality: str | None = None


class TesterRequest(ReasonRequest):
    can_demo: bool


@router.get("/admin/demo")
async def admin_overview(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Demo mode at a glance: whether it's on, the runs, testers and every club."""
    from app.clubs.models import Club
    from app.config import settings

    runs = (await db.execute(select(DemoRun).order_by(DemoRun.started_at.desc()).limit(50))).scalars().all()
    users = {u.id: u for u in (await db.execute(select(User).where(
        User.id.in_({r.user_id for r in runs}) | User.can_demo.is_(True)))).scalars()}
    clubs = (await db.execute(select(Club).order_by(Club.name))).scalars().all()
    return {
        "enabled": settings.demo_enabled,
        "runs": [{**(await service.describe(db, r)), "user": users[r.user_id].display_label if r.user_id in users else None}
                 for r in runs],
        "testers": [{"id": str(u.id), "name": u.display_label} for u in users.values() if u.can_demo],
        "clubs": [{"id": str(c.id), "name": c.name, "house_club": c.house_club, "personality": c.house_personality,
                   "in_use": await service.club_in_use(db, c)} for c in clubs],
    }


@router.patch("/admin/demo/clubs/{club_id}")
async def set_house_club(
    club_id: uuid.UUID,
    body: HouseClubRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Make a club a house club (TransferX plays it in demos), or stop. Only
    a club nobody uses can become one. Audited with the reason."""
    from app.admin import audit as admin_audit
    from app.clubs.models import Club

    club = await db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    if body.house_club and await service.club_in_use(db, club):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"People use {club.name}, so TransferX can't play it in demos.")
    if body.personality is not None and body.personality not in service.PERSONALITIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Personality is hard, fair or eager.")
    club.house_club = body.house_club
    club.house_personality = (body.personality or club.house_personality or "fair") if body.house_club else None
    await admin_audit.record(
        db, current_user, "demo.house_club_set", entity_type="club", entity_id=club.id, reason=body.reason,
        description=f"{'Made' if body.house_club else 'Stopped'} {club.name} {'a' if body.house_club else 'being a'} house club",
        details={"house_club": club.house_club, "personality": club.house_personality},
    )
    await db.commit()
    return {"id": str(club.id), "house_club": club.house_club, "personality": club.house_personality}


@router.patch("/admin/demo/testers/{user_id}")
async def set_tester(
    user_id: uuid.UUID,
    body: TesterRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Let someone start demos, or stop them. Audited with the reason."""
    from app.admin import audit as admin_audit

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.can_demo = body.can_demo
    await admin_audit.record(
        db, current_user, "demo.tester_set", entity_type="user", entity_id=user.id, reason=body.reason,
        description=f"{'Let' if body.can_demo else 'Stopped'} {user.display_label} {'start' if body.can_demo else 'starting'} demos",
        details={"can_demo": body.can_demo},
    )
    await db.commit()
    return {"id": str(user.id), "can_demo": user.can_demo}


@router.post("/admin/demo/runs/{run_id}/reset")
async def admin_reset(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset anyone's demo."""
    run = await db.get(DemoRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo not found")
    try:
        report = await service.reset(db, run, by_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await db.commit()
    return report
