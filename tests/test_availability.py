"""Opening hours and the pause toggle (epic4.task3)."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Restaurant, RestaurantHours
from app.models.enums import RestaurantStaffRole
from app.services.availability import Window, find_overlap, is_accepting_orders, is_open
from tests.factories import auth, create_restaurant, staffed_restaurant

LA = "America/Los_Angeles"
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


def local(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """A moment given in Los Angeles wall-clock time, converted to UTC like the API's now."""
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(LA)).astimezone(UTC)


# 2026-11-23 is a Monday.
def mon(hour: int, minute: int = 0) -> datetime:
    return local(2026, 11, 23, hour, minute)


# --- The open/closed calculation -------------------------------------------------


def test_simple_window() -> None:
    hours = [Window(MON, time(9), time(17))]
    assert not is_open(hours, LA, mon(8, 59))
    assert is_open(hours, LA, mon(9, 0))
    assert is_open(hours, LA, mon(16, 59))
    assert not is_open(hours, LA, mon(17, 0))  # closing time is exclusive
    assert not is_open(hours, LA, local(2026, 11, 24, 10))  # Tuesday


def test_several_windows_in_one_day() -> None:
    hours = [Window(MON, time(11), time(14)), Window(MON, time(17), time(22))]
    assert is_open(hours, LA, mon(12))
    assert not is_open(hours, LA, mon(15))
    assert is_open(hours, LA, mon(21, 30))


def test_window_past_midnight_belongs_to_the_day_it_opens() -> None:
    hours = [Window(FRI, time(17), time(1))]  # Friday 17:00 to Saturday 01:00
    assert is_open(hours, LA, local(2026, 11, 27, 23))  # Friday night
    assert is_open(hours, LA, local(2026, 11, 28, 0, 30))  # early Saturday
    assert not is_open(hours, LA, local(2026, 11, 28, 1))
    assert not is_open(hours, LA, local(2026, 11, 27, 0, 30))  # early Friday: Thursday's slot


def test_sunday_night_window_wraps_to_monday() -> None:
    hours = [Window(SUN, time(20), time(2))]
    assert is_open(hours, LA, local(2026, 11, 29, 21))  # Sunday
    assert is_open(hours, LA, local(2026, 11, 30, 1))  # Monday morning
    assert not is_open(hours, LA, local(2026, 11, 30, 3))


def test_equal_times_mean_24_hours() -> None:
    hours = [Window(MON, time(0), time(0))]
    assert is_open(hours, LA, mon(0))
    assert is_open(hours, LA, mon(23, 59))
    assert not is_open(hours, LA, local(2026, 11, 24, 0))


def test_no_hours_means_closed() -> None:
    assert not is_open([], LA, mon(12))


def test_hours_are_local_time_across_daylight_saving() -> None:
    # 9:00-17:00 local is 17:00-01:00 UTC in winter (PST) and 16:00-00:00 UTC in
    # summer (PDT). Both are Mondays.
    hours = [Window(MON, time(9), time(17))]
    winter = datetime(2026, 1, 5, 16, 30, tzinfo=UTC)  # 08:30 PST
    summer = datetime(2026, 7, 6, 16, 30, tzinfo=UTC)  # 09:30 PDT
    assert not is_open(hours, LA, winter)
    assert is_open(hours, LA, summer)


def test_night_the_clocks_go_back() -> None:
    # 2026-11-01 (Sunday): 01:00-02:00 happens twice in Los Angeles. A window open
    # until 01:30 covers both, since it's wall-clock time.
    hours = [Window(SAT, time(22), time(1, 30))]
    first = datetime(2026, 11, 1, 8, 15, tzinfo=UTC)  # 01:15 PDT
    second = datetime(2026, 11, 1, 9, 15, tzinfo=UTC)  # 01:15 PST
    assert is_open(hours, LA, first) and is_open(hours, LA, second)
    assert not is_open(hours, LA, datetime(2026, 11, 1, 10, 0, tzinfo=UTC))  # 02:00 PST


def test_night_the_clocks_go_forward() -> None:
    # 2026-03-08 (Sunday): 02:00-03:00 doesn't exist in Los Angeles.
    hours = [Window(SUN, time(1), time(2, 30))]
    assert is_open(hours, LA, datetime(2026, 3, 8, 9, 30, tzinfo=UTC))  # 01:30 PST
    assert not is_open(hours, LA, datetime(2026, 3, 8, 10, 0, tzinfo=UTC))  # 03:00 PDT


def test_timezone_is_the_restaurants() -> None:
    hours = [Window(MON, time(9), time(17))]
    moment = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)  # 10:00 New York, 07:00 LA
    assert is_open(hours, "America/New_York", moment)
    assert not is_open(hours, LA, moment)


@pytest.mark.parametrize(
    ("a", "b", "overlaps"),
    [
        (Window(MON, time(9), time(15)), Window(MON, time(14), time(18)), True),
        (Window(MON, time(9), time(15)), Window(MON, time(15), time(18)), False),  # touching
        (Window(MON, time(18), time(2)), Window(TUE, time(1), time(9)), True),
        (Window(MON, time(18), time(2)), Window(TUE, time(2), time(9)), False),
        (Window(SUN, time(20), time(3)), Window(MON, time(2), time(9)), True),  # wraps
        (Window(MON, time(0), time(0)), Window(MON, time(12), time(13)), True),
        (Window(MON, time(9), time(17)), Window(TUE, time(9), time(17)), False),
    ],
)
def test_find_overlap(a: Window, b: Window, overlaps: bool) -> None:
    assert (find_overlap([a, b]) is not None) == overlaps
    assert (find_overlap([b, a]) is not None) == overlaps


def test_accepting_orders_needs_active_unpaused_and_open() -> None:
    hours = [Window(MON, time(9), time(17))]
    restaurant = Restaurant(name="R", address="A", timezone=LA, is_active=True)
    assert is_accepting_orders(restaurant, hours, mon(12))
    assert not is_accepting_orders(restaurant, hours, mon(20))

    restaurant.orders_paused_at = mon(11)
    assert not is_accepting_orders(restaurant, hours, mon(12))

    restaurant.orders_paused_at = None
    restaurant.is_active = False
    assert not is_accepting_orders(restaurant, hours, mon(12))


# --- Endpoints ---------------------------------------------------------------------

ALL_WEEK = [
    {"day": d, "opens_at": "00:00", "closes_at": "00:00"}
    for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
]


async def test_new_restaurant_has_no_hours_and_is_closed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)

    response = await client.get(f"/restaurants/{restaurant.id}/availability", headers=auth(staff))

    assert response.status_code == 200
    body = response.json()
    assert body["hours"] == []
    assert body["is_open_now"] is False
    assert body["accepting_orders"] is False
    assert body["orders_paused_at"] is None


async def test_manager_sets_hours(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, manager = await staffed_restaurant(db_session, RestaurantStaffRole.MANAGER)
    url = f"/restaurants/{restaurant.id}/hours"

    response = await client.put(url, json={"hours": ALL_WEEK}, headers=auth(manager))
    assert response.status_code == 200
    body = response.json()
    assert body["is_open_now"] is True and body["accepting_orders"] is True
    assert [h["day"] for h in body["hours"]][:2] == ["monday", "tuesday"]
    assert body["hours"][0]["opens_at"] == "00:00:00"

    # Replacing, not adding: the new schedule is exactly what was sent.
    lunch = [
        {"day": "friday", "opens_at": "17:00", "closes_at": "22:00"},
        {"day": "friday", "opens_at": "11:00", "closes_at": "14:00"},
    ]
    response = await client.put(url, json={"hours": lunch}, headers=auth(manager))
    assert [(h["opens_at"], h["closes_at"]) for h in response.json()["hours"]] == [
        ("11:00:00", "14:00:00"),
        ("17:00:00", "22:00:00"),
    ]
    rows = await db_session.scalars(
        select(RestaurantHours).where(RestaurantHours.restaurant_id == restaurant.id)
    )
    assert len(rows.all()) == 2


async def test_overlapping_or_invalid_hours_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, manager = await staffed_restaurant(db_session, RestaurantStaffRole.MANAGER)
    url = f"/restaurants/{restaurant.id}/hours"

    overlap = [
        {"day": "monday", "opens_at": "18:00", "closes_at": "02:00"},
        {"day": "tuesday", "opens_at": "01:00", "closes_at": "09:00"},
    ]
    response = await client.put(url, json={"hours": overlap}, headers=auth(manager))
    assert response.status_code == 422
    assert "overlap" in response.text

    for bad in [
        {"day": "funday", "opens_at": "09:00", "closes_at": "17:00"},
        {"day": "monday", "opens_at": "09:00:30", "closes_at": "17:00"},
        {"day": "monday", "opens_at": "25:00", "closes_at": "17:00"},
    ]:
        response = await client.put(url, json={"hours": [bad]}, headers=auth(manager))
        assert response.status_code == 422, bad


async def test_staff_cannot_set_hours(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)

    response = await client.put(
        f"/restaurants/{restaurant.id}/hours", json={"hours": ALL_WEEK}, headers=auth(staff)
    )
    assert response.status_code == 403


async def test_staff_pause_and_resume(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    db_session.add_all(
        RestaurantHours(
            restaurant_id=restaurant.id, day_of_week=d, opens_at=time(0), closes_at=time(0)
        )
        for d in range(7)
    )
    await db_session.flush()
    url = f"/restaurants/{restaurant.id}/pause"

    paused = await client.put(url, json={"paused": True}, headers=auth(staff))
    assert paused.status_code == 200
    assert paused.json()["orders_paused_at"] is not None
    assert paused.json()["is_open_now"] is True
    assert paused.json()["accepting_orders"] is False

    # Pausing again keeps the original time.
    again = await client.put(url, json={"paused": True}, headers=auth(staff))
    assert again.json()["orders_paused_at"] == paused.json()["orders_paused_at"]

    resumed = await client.put(url, json={"paused": False}, headers=auth(staff))
    assert resumed.json()["orders_paused_at"] is None
    assert resumed.json()["accepting_orders"] is True


async def test_other_restaurants_staff_are_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, outsider = await staffed_restaurant(db_session, RestaurantStaffRole.OWNER)
    other = await create_restaurant(db_session, name="Other")

    for method, path, body in [
        ("GET", "availability", None),
        ("PUT", "hours", {"hours": ALL_WEEK}),
        ("PUT", "pause", {"paused": True}),
    ]:
        response = await client.request(
            method, f"/restaurants/{other.id}/{path}", json=body, headers=auth(outsider)
        )
        assert response.status_code == 403, path
