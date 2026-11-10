from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, Field

from app.models.enums import RestaurantStaffRole
from app.schemas.auth import NewPassword
from app.schemas.base import ORMBase, PatchModel

# Deliberately loose: catches typos, not every invalid address. Real verification
# needs an email provider, which doesn't exist yet (see EPIC3_TRACKER.md epic3.task2).
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(
            "Unknown timezone, expected an IANA name like America/Los_Angeles"
        ) from exc
    return value


Timezone = Annotated[str, Field(max_length=50), AfterValidator(_validate_timezone)]
# Lowercased so adding "Owner@Example.com" finds the existing owner@example.com account.
Email = Annotated[str, Field(max_length=255, pattern=EMAIL_PATTERN), AfterValidator(str.lower)]


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=500)
    timezone: Timezone = "America/Los_Angeles"


class RestaurantUpdate(PatchModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    timezone: Timezone | None = None
    is_active: bool | None = None


class RestaurantOut(ORMBase):
    id: int
    name: str
    address: str
    timezone: str
    is_active: bool


class StaffCreate(BaseModel):
    """Add someone to a restaurant's staff by email. If the email has no account yet,
    `full_name` and a temporary `password` create one; if it does, leave both out."""

    email: Email
    role: RestaurantStaffRole
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    password: NewPassword | None = None


class StaffUpdate(BaseModel):
    role: RestaurantStaffRole


class StaffOut(BaseModel):
    user_id: int
    email: str
    full_name: str
    role: RestaurantStaffRole
