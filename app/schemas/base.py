from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, model_validator


class ORMBase(BaseModel):
    """Base for response schemas that read directly from SQLAlchemy model instances."""

    model_config = ConfigDict(from_attributes=True)


class PatchModel(BaseModel):
    """Base for PATCH bodies: fields left out stay unchanged. An explicit null is only
    allowed for fields listed in `clearable`, since the rest are NOT NULL columns."""

    clearable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_nulls(self) -> Self:
        nulls = sorted(
            f for f in self.model_fields_set if getattr(self, f) is None and f not in self.clearable
        )
        if nulls:
            raise ValueError(f"Cannot be null: {', '.join(nulls)}")
        return self
