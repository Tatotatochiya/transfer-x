from fastapi import APIRouter

from app.fx import service

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/rates")
async def rates() -> dict:
    """£1 in EUR and USD, for display estimates. Public: no club data."""
    return await service.get_rates()
