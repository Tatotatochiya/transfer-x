"""B2 — Dashboard aggregate endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clubs import service as clubs_service
from app.dashboard import service
from app.dashboard.schemas import DashboardResponse
from app.database import get_db
from app.deps import get_current_user

router = APIRouter(tags=["dashboard"])


@router.get("/clubs/me/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return await service.get_dashboard(db, club=club, current_user=current_user)
