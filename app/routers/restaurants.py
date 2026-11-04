from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import Role, require_restaurant_role, require_role
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Restaurant, RestaurantStaff, User
from app.models.enums import RestaurantStaffRole
from app.schemas.restaurant import (
    RestaurantCreate,
    RestaurantOut,
    RestaurantUpdate,
    StaffCreate,
    StaffOut,
    StaffUpdate,
)

router = APIRouter(prefix="/restaurants", tags=["restaurants"])

LAST_OWNER_DETAIL = "A restaurant must keep at least one owner"


def _staff_out(membership: RestaurantStaff) -> StaffOut:
    return StaffOut(
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
    )


async def _get_membership(db: AsyncSession, restaurant_id: int, user_id: int) -> RestaurantStaff:
    result = await db.execute(
        select(RestaurantStaff)
        .options(selectinload(RestaurantStaff.user))
        .where(RestaurantStaff.restaurant_id == restaurant_id, RestaurantStaff.user_id == user_id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    return membership


async def _ensure_another_owner(db: AsyncSession, restaurant_id: int) -> None:
    """Raise unless the restaurant has more than one owner. Locks the restaurant row
    first so two concurrent requests can't each remove a different last-but-one owner."""
    await db.execute(select(Restaurant.id).where(Restaurant.id == restaurant_id).with_for_update())
    owners = await db.scalar(
        select(func.count())
        .select_from(RestaurantStaff)
        .where(
            RestaurantStaff.restaurant_id == restaurant_id,
            RestaurantStaff.role == RestaurantStaffRole.OWNER,
        )
    )
    if (owners or 0) <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=LAST_OWNER_DETAIL)


@router.post("", response_model=RestaurantOut, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    payload: RestaurantCreate,
    _: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Restaurant:
    restaurant = Restaurant(**payload.model_dump())
    db.add(restaurant)
    await db.commit()
    return restaurant


@router.get("/{restaurant_id}", response_model=RestaurantOut)
async def get_restaurant(
    restaurant: Restaurant = Depends(require_restaurant_role(RestaurantStaffRole.STAFF)),
) -> Restaurant:
    return restaurant


@router.patch("/{restaurant_id}", response_model=RestaurantOut)
async def update_restaurant(
    restaurant_id: int,
    payload: RestaurantUpdate,
    _: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Restaurant:
    restaurant = await db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    await db.commit()
    return restaurant


@router.get("/{restaurant_id}/staff", response_model=list[StaffOut])
async def list_staff(
    restaurant: Restaurant = Depends(require_restaurant_role(RestaurantStaffRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[StaffOut]:
    result = await db.execute(
        select(RestaurantStaff)
        .options(selectinload(RestaurantStaff.user))
        .where(RestaurantStaff.restaurant_id == restaurant.id)
        .order_by(RestaurantStaff.id)
    )
    return [_staff_out(m) for m in result.scalars()]


@router.post("/{restaurant_id}/staff", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
async def add_staff(
    payload: StaffCreate,
    restaurant: Restaurant = Depends(require_restaurant_role(RestaurantStaffRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> StaffOut:
    user = await db.scalar(select(User).where(func.lower(User.email) == payload.email))
    if user is not None:
        if payload.full_name is not None or payload.password is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists; "
                "leave out full_name and password to add it",
            )
        already_staff = await db.scalar(
            select(RestaurantStaff.id).where(
                RestaurantStaff.restaurant_id == restaurant.id, RestaurantStaff.user_id == user.id
            )
        )
        if already_staff is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Already on this restaurant's staff"
            )
    else:
        if payload.full_name is None or payload.password is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No account with this email; full_name and password are required",
            )
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
        db.add(user)

    # restaurant_id rather than restaurant=, so the backref doesn't need restaurant.staff loaded.
    membership = RestaurantStaff(user=user, restaurant_id=restaurant.id, role=payload.role)
    db.add(membership)
    try:
        await db.commit()
    except IntegrityError as exc:
        # Lost a race with a concurrent request creating the same account or membership.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account or staff membership already exists",
        ) from exc
    return _staff_out(membership)


@router.patch("/{restaurant_id}/staff/{user_id}", response_model=StaffOut)
async def update_staff_role(
    user_id: int,
    payload: StaffUpdate,
    restaurant: Restaurant = Depends(require_restaurant_role(RestaurantStaffRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> StaffOut:
    membership = await _get_membership(db, restaurant.id, user_id)
    if membership.role == RestaurantStaffRole.OWNER and payload.role != RestaurantStaffRole.OWNER:
        await _ensure_another_owner(db, restaurant.id)
    membership.role = payload.role
    await db.commit()
    return _staff_out(membership)


@router.delete("/{restaurant_id}/staff/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(
    user_id: int,
    restaurant: Restaurant = Depends(require_restaurant_role(RestaurantStaffRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    membership = await _get_membership(db, restaurant.id, user_id)
    if membership.role == RestaurantStaffRole.OWNER:
        await _ensure_another_owner(db, restaurant.id)
    # Only the staff link goes; the user's account (and any other roles) stays.
    await db.delete(membership)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
