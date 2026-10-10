import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.models import User
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth_service.decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc
    # "View as this club" (admin panel): staff see the club's own screens,
    # but nothing can be changed. Every request that could change something
    # is refused here, before any endpoint runs.
    if payload.get("ro"):
        if request.method not in auth_service.SAFE_METHODS:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=auth_service.READ_ONLY_DETAIL)
        request.state.view_as_by = payload.get("act")

    # Signed out on another device (Account settings → Signed-in devices).
    if payload.get("sid") and not await auth_service.session_alive(db, payload["sid"]):
        raise credentials_exc
    user = await auth_service.get_user_by_id(db, uuid.UUID(user_id_str))
    if user is None or not user.is_active:
        raise credentials_exc
    from app.monitoring.context import set_user

    set_user(user.id)  # error tracking: which user a request's errors were for
    return user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return current_user
