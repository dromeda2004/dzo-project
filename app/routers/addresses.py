"""A customer's saved delivery addresses (epic4.task2).

An address an order has used is never changed or deleted, so the order keeps showing
where it was delivered. Deleting it archives it instead, and editing it archives it and
saves the edited copy as a new address with a new id.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import Address, Order, User
from app.schemas.address import AddressCreate, AddressOut, AddressUpdate

router = APIRouter(prefix="/me/addresses", tags=["addresses"])

# Plenty for home, work and a few others; stops one account filling the table.
MAX_ADDRESSES = 20

_LOCATION = {"line1", "line2", "city", "state", "postal_code"}
_COPIED = ("line1", "line2", "city", "state", "postal_code", "delivery_instructions")


async def _get_address(db: AsyncSession, user: User, address_id: int) -> Address:
    address = await db.scalar(
        select(Address).where(
            Address.id == address_id,
            Address.user_id == user.id,
            Address.is_archived.is_(False),
        )
    )
    if address is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    return address


async def _used_by_an_order(db: AsyncSession, address: Address) -> bool:
    return bool(await db.scalar(select(exists().where(Order.delivery_address_id == address.id))))


@router.get("", response_model=list[AddressOut])
async def list_addresses(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Address]:
    result = await db.scalars(
        select(Address)
        .where(Address.user_id == user.id, Address.is_archived.is_(False))
        .order_by(Address.id)
    )
    return list(result)


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(
    payload: AddressCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Address:
    count = await db.scalar(
        select(func.count())
        .select_from(Address)
        .where(Address.user_id == user.id, Address.is_archived.is_(False))
    )
    if (count or 0) >= MAX_ADDRESSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You can save at most {MAX_ADDRESSES} addresses; delete one first",
        )
    address = Address(user_id=user.id, **payload.model_dump())
    db.add(address)
    await db.commit()
    return address


@router.get("/{address_id}", response_model=AddressOut)
async def get_address(
    address_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Address:
    return await _get_address(db, user, address_id)


@router.patch("/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: int,
    payload: AddressUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Address:
    """Returns the updated address. If an order has used it, that's a new address with a
    new id, and the old id stops working."""
    address = await _get_address(db, user, address_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return address
    if await _used_by_an_order(db, address):
        address.is_archived = True
        fields = {f: getattr(address, f) for f in _COPIED} | changes
        address = Address(user_id=user.id, **fields)
        db.add(address)
    else:
        for field, value in changes.items():
            setattr(address, field, value)
        if changes.keys() & _LOCATION:
            # The coordinates belonged to the old location; geocoding refills them (Epic 6).
            address.latitude = address.longitude = None
    await db.commit()
    return address


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    address = await _get_address(db, user, address_id)
    if await _used_by_an_order(db, address):
        address.is_archived = True
    else:
        await db.delete(address)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
