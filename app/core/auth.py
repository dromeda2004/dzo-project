import enum
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Restaurant, User
from app.models.enums import RestaurantStaffRole

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class Role(enum.StrEnum):
    """Roles are derived from a user's data, not stored as a single column on
    User (see app/models/user.py) — a person can hold more than one role.
    """

    CUSTOMER = "customer"
    DRIVER = "driver"
    MERCHANT = "merchant"
    ADMIN = "admin"


def create_access_token(user_id: int) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return int(subject)


def user_roles(user: User) -> set[Role]:
    roles = {Role.CUSTOMER}
    if user.driver_profile is not None:
        roles.add(Role.DRIVER)
    if user.restaurant_staff_memberships:
        roles.add(Role.MERCHANT)
    if user.is_admin:
        roles.add(Role.ADMIN)
    return roles


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_access_token(token)
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.driver_profile),
            selectinload(User.restaurant_staff_memberships),
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    return user


def require_role(role: Role) -> Callable[[User], Coroutine[Any, Any, User]]:
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if role not in user_roles(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency


# Higher rank can do everything a lower rank can — see docs/EPIC3_TRACKER.md epic3.task1.
RESTAURANT_ROLE_RANK = {
    RestaurantStaffRole.STAFF: 0,
    RestaurantStaffRole.MANAGER: 1,
    RestaurantStaffRole.OWNER: 2,
}


def require_restaurant_role(
    min_role: RestaurantStaffRole,
) -> Callable[..., Coroutine[Any, Any, Restaurant]]:
    """Gate a route on the path's `restaurant_id`: the user must be on that
    restaurant's staff with at least `min_role`. Internal admins pass for any
    restaurant. Unlike require_role(Role.MERCHANT), being staff at some *other*
    restaurant isn't enough.
    """

    async def dependency(
        restaurant_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Restaurant:
        restaurant = await db.get(Restaurant, restaurant_id)
        if restaurant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found"
            )
        # Admin access goes through user_roles so it stays one check to change once
        # HQ users get permission levels (EPIC1_TRACKER.md epic1.task3 open items).
        if Role.ADMIN in user_roles(user):
            return restaurant
        membership = next(
            (m for m in user.restaurant_staff_memberships if m.restaurant_id == restaurant_id),
            None,
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not on this restaurant's staff"
            )
        if RESTAURANT_ROLE_RANK[membership.role] < RESTAURANT_ROLE_RANK[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient restaurant role"
            )
        return restaurant

    return dependency
