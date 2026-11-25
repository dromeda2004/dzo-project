"""Opening hours and the pause toggle (epic4.task3)."""

import enum
from datetime import datetime, time
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.availability import Window, find_overlap


class Weekday(enum.StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @property
    def number(self) -> int:
        """Monday = 0 ... Sunday = 6, as stored."""
        return list(Weekday).index(self)

    @classmethod
    def at(cls, index: int) -> "Weekday":
        return list(cls)[index]


class HoursWindow(BaseModel):
    """One opening window in the restaurant's local time, e.g. `{"day": "friday",
    "opens_at": "17:00", "closes_at": "01:00"}`. A `closes_at` at or before `opens_at`
    means the window ends the next day; equal times mean open for 24 hours."""

    day: Weekday
    opens_at: time
    closes_at: time

    @field_validator("opens_at", "closes_at")
    @classmethod
    def _whole_minutes(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("Give a local time without a timezone, e.g. 17:00")
        if value.second or value.microsecond:
            raise ValueError("Use whole minutes, e.g. 17:00")
        return value

    def window(self) -> Window:
        return Window(self.day.number, self.opens_at, self.closes_at)

    @classmethod
    def of(cls, window: Window) -> "HoursWindow":
        return cls(
            day=Weekday.at(window.day_of_week), opens_at=window.opens_at, closes_at=window.closes_at
        )


class HoursUpdate(BaseModel):
    """The full weekly schedule; it replaces whatever was there. An empty list means
    the restaurant is never open."""

    hours: list[HoursWindow] = Field(max_length=28)

    @model_validator(mode="after")
    def _no_overlaps(self) -> Self:
        clash = find_overlap(w.window() for w in self.hours)
        if clash:
            a, b = (HoursWindow.of(w) for w in clash)
            raise ValueError(
                f"Opening windows overlap: {a.day} {a.opens_at:%H:%M}-{a.closes_at:%H:%M} "
                f"and {b.day} {b.opens_at:%H:%M}-{b.closes_at:%H:%M}"
            )
        return self


class PauseUpdate(BaseModel):
    paused: bool


class AvailabilityOut(BaseModel):
    timezone: str
    hours: list[HoursWindow]
    is_active: bool
    # When staff paused new orders; null when not paused.
    orders_paused_at: datetime | None
    is_open_now: bool
    # Active, not paused, and open: what checkout checks.
    accepting_orders: bool
