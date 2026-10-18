"""Regression tests for per-meeting online/offline scheduling."""

import pytest
from werkzeug.datastructures import MultiDict

from app import create_app
from app.blueprints.admin import _aggregate_delivery_mode as admin_aggregate_mode
from app.blueprints.admin import _submitted_schedule_slots
from app.blueprints.lecturer import _aggregate_delivery_mode as lecturer_aggregate_mode
from app.blueprints.lecturer import _slots_from_form


@pytest.fixture()
def app():
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "schedule-test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
        "IDENTITY_PROVIDER": "sample",
    })


MIXED_SLOT_FORM = MultiDict([
    ("weekday[]", "0"),
    ("weekday[]", "2"),
    ("start_time[]", "08:00"),
    ("start_time[]", "13:00"),
    ("end_time[]", "09:40"),
    ("end_time[]", "14:40"),
    ("delivery_mode[]", "OFFLINE"),
    ("delivery_mode[]", "ONLINE"),
    # These fields remain submitted for every row even when the meeting URL
    # input is visually hidden on the offline row and room is read-only online.
    ("room[]", "B3.1"),
    ("room[]", "Online"),
    ("online_url[]", ""),
    ("online_url[]", "https://meet.google.com/test-room"),
])


@pytest.mark.parametrize(
    ("parser", "aggregate_mode"),
    [
        (_submitted_schedule_slots, admin_aggregate_mode),
        (_slots_from_form, lecturer_aggregate_mode),
    ],
)
def test_mixed_weekly_slots_keep_each_mode_room_and_link(app, parser, aggregate_mode):
    with app.test_request_context("/", method="POST", data=MIXED_SLOT_FORM):
        slots = parser()

    assert len(slots) == 2
    assert slots[0]["delivery_mode"] == "OFFLINE"
    assert slots[0]["room"] == "B3.1"
    assert slots[0]["online_url"] is None
    assert slots[1]["delivery_mode"] == "ONLINE"
    assert slots[1]["room"] == "Online"
    assert slots[1]["online_url"] == "https://meet.google.com/test-room"
    assert aggregate_mode(slots) == "MIXED"


@pytest.mark.parametrize("parser", [_submitted_schedule_slots, _slots_from_form])
def test_weekly_slots_reject_invalid_online_url(app, parser):
    form = MultiDict([
        ("weekday[]", "1"),
        ("start_time[]", "10:00"),
        ("end_time[]", "11:00"),
        ("delivery_mode[]", "ONLINE"),
        ("room[]", "Online"),
        ("online_url[]", "javascript:alert(1)"),
    ])
    with app.test_request_context("/", method="POST", data=form):
        with pytest.raises(ValueError, match="http:// atau https://"):
            parser()
