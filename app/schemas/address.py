"""Customer delivery addresses (epic4.task2)."""

from typing import Annotated, ClassVar

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.schemas.base import ORMBase, PatchModel


def _blank_to_none(value: str) -> str | None:
    return value or None


# Required text: trimmed, then at least one character.
Line1 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
City = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
State = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
PostalCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
# Optional text: trimmed, and blank becomes null.
Line2 = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=255), AfterValidator(_blank_to_none)
]
Instructions = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=500), AfterValidator(_blank_to_none)
]


class AddressCreate(BaseModel):
    line1: Line1
    line2: Line2 | None = None
    city: City
    state: State
    postal_code: PostalCode
    delivery_instructions: Instructions | None = None


class AddressUpdate(PatchModel):
    clearable: ClassVar[frozenset[str]] = frozenset({"line2", "delivery_instructions"})

    line1: Line1 | None = None
    line2: Line2 | None = None
    city: City | None = None
    state: State | None = None
    postal_code: PostalCode | None = None
    delivery_instructions: Instructions | None = None


class AddressOut(ORMBase):
    id: int
    line1: str
    line2: str | None
    city: str
    state: str
    postal_code: str
    delivery_instructions: str | None
