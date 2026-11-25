"""Is a restaurant open, and is it taking orders right now? (epic4.task3)

Opening hours are wall-clock times in the restaurant's own timezone, so "9:00-17:00"
means 9 to 5 local time on both sides of a daylight-saving change.

Each window is turned into a span of minutes within the week (Monday 00:00 = 0). A
window that runs past midnight on Sunday wraps around to Monday morning.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.models import Restaurant, RestaurantHours

MINUTES_PER_DAY = 24 * 60
MINUTES_PER_WEEK = 7 * MINUTES_PER_DAY


@dataclass(frozen=True)
class Window:
    day_of_week: int  # Monday = 0
    opens_at: time
    closes_at: time

    @classmethod
    def of(cls, row: RestaurantHours) -> "Window":
        return cls(row.day_of_week, row.opens_at, row.closes_at)

    def span(self) -> tuple[int, int]:
        """(start, end) in minutes from Monday 00:00. `end` can pass the end of the
        week when the window runs past Sunday midnight."""
        start = self.day_of_week * MINUTES_PER_DAY + _minute_of_day(self.opens_at)
        length = (_minute_of_day(self.closes_at) - _minute_of_day(self.opens_at)) % MINUTES_PER_DAY
        return start, start + (length or MINUTES_PER_DAY)


def _minute_of_day(t: time) -> int:
    return t.hour * 60 + t.minute


def _pieces(window: Window) -> list[tuple[int, int]]:
    """The window's span, split at the end of the week if it wraps."""
    start, end = window.span()
    if end <= MINUTES_PER_WEEK:
        return [(start, end)]
    return [(start, MINUTES_PER_WEEK), (0, end - MINUTES_PER_WEEK)]


def find_overlap(windows: Iterable[Window]) -> tuple[Window, Window] | None:
    """Two windows that overlap, if any. Touching windows (one closes at 15:00,
    the next opens at 15:00) don't count."""
    pieces = sorted((s, e, w) for w in windows for s, e in _pieces(w))
    for (_, end, first), (start, _, second) in zip(pieces, pieces[1:], strict=False):
        if start < end:
            return first, second
    return None


def is_open(windows: Iterable[Window], timezone: str, now: datetime) -> bool:
    local = now.astimezone(ZoneInfo(timezone))
    minute = local.weekday() * MINUTES_PER_DAY + local.hour * 60 + local.minute
    return any(s <= minute < e for w in windows for s, e in _pieces(w))


def is_accepting_orders(restaurant: Restaurant, windows: Iterable[Window], now: datetime) -> bool:
    """Active, not paused, and inside its opening hours. Checkout (epic4.task6) refuses
    orders otherwise."""
    return (
        restaurant.is_active
        and restaurant.orders_paused_at is None
        and is_open(windows, restaurant.timezone, now)
    )
