"""Fixtures endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.auth.models import User
from app.vendor.client import ApiFootballClient
from app.fixtures import service as fixture_service
from app.fixtures.schemas import FixtureResponse

router = APIRouter(prefix="/fixtures", tags=["fixtures"])


def _get_client() -> ApiFootballClient:
    if not settings.apisports_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APISPORTS_KEY not configured",
        )
    return ApiFootballClient(settings.apisports_key, settings.api_football_base_url)


@router.get("/team/{vendor_team_id}", response_model=list[FixtureResponse])
async def get_team_fixtures(
    vendor_team_id: int,
    next: int = 5,
    last: int = 5,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return recent + upcoming fixtures for a vendor team ID.
    Served from cache; refreshed automatically if older than 1 hour.
    """
    client = _get_client()
    try:
        fixtures = await fixture_service.get_team_fixtures(
            db, vendor_team_id, client, next_count=next, last_count=last
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return [FixtureResponse.model_validate(f) for f in fixtures]
