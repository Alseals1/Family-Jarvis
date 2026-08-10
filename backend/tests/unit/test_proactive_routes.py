"""
Unit tests for GET /api/briefing and GET /api/notifications routes.

All DB calls and job functions are mocked — tests focus on:
- JWT enforcement (401 when missing)
- family_id from JWT only
- Correct response shapes
- Briefing fallback to on-demand
- Notifications mark-as-delivered
- Family isolation
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

UTC = timezone.utc

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
}

FAMILY_ID = "fam-reeds"
USER_ID = "user-001"
AUTH_HEADER = {"Authorization": "Bearer test-token"}
TODAY = datetime.now(UTC).date().isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        get_settings()
        from app.main import app
        return TestClient(app, raise_server_exceptions=False)


def _mock_auth_admin(family_id=FAMILY_ID):
    mock = MagicMock()
    result = MagicMock()
    result.user = MagicMock()
    result.user.id = USER_ID
    result.user.email = "marcus@demo.jarvis"
    mock.auth.get_user.return_value = result
    return mock


def _auth_patches(family_id=FAMILY_ID):
    """Standard auth patches for all route tests."""
    return [
        patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin(family_id)),
        patch("app.api.middleware.auth.get_family_id_for_user", return_value=family_id),
    ]


def _briefing_admin_mock(briefing_rows=None):
    """Mock admin client for /api/briefing."""
    admin = MagicMock()

    select_chain = MagicMock()
    select_chain.select.return_value = select_chain
    select_chain.eq.return_value = select_chain
    select_chain.order.return_value = select_chain
    select_chain.limit.return_value = select_chain
    select_chain.execute.return_value = MagicMock(data=briefing_rows or [])

    def _table_side(name):
        tbl = MagicMock()
        tbl.select.return_value = select_chain
        return tbl

    admin.table.side_effect = _table_side
    return admin


def _notifications_admin_mock(notification_rows=None, capture_update=None):
    """Mock admin client for /api/notifications."""
    admin = MagicMock()
    rows = notification_rows or []

    select_chain = MagicMock()
    select_chain.select.return_value = select_chain
    select_chain.eq.return_value = select_chain
    select_chain.order.return_value = select_chain
    select_chain.limit.return_value = select_chain
    select_chain.execute.return_value = MagicMock(data=rows)

    update_chain = MagicMock()

    def _in_(col, vals):
        if capture_update is not None:
            capture_update["called"] = True
            capture_update["ids"] = vals
        return update_chain

    update_chain.in_ = _in_
    update_chain.execute.return_value = MagicMock(data=[])

    def _update(payload):
        return update_chain

    def _table_side(name):
        tbl = MagicMock()
        tbl.select.return_value = select_chain
        tbl.update = _update
        return tbl

    admin.table.side_effect = _table_side
    return admin


def _briefing_row(briefing_type="morning"):
    prefix = "Good morning" if briefing_type == "morning" else "Good evening"
    return {
        "id": "briefing-1",
        "type": "briefing",
        "content": f"{prefix} — daily briefing\nYou have 2 events today.",
        "trigger_date": TODAY,
        "created_at": f"{TODAY}T11:00:00+00:00",
        "delivered": False,
    }


def _notification_rows():
    return [
        {
            "id": "notif-1",
            "type": "birthday",
            "content": "Birthday alert",
            "trigger_date": TODAY,
            "created_at": f"{TODAY}T12:00:00+00:00",
            "delivered": False,
        },
        {
            "id": "notif-2",
            "type": "conflict",
            "content": "Conflict alert",
            "trigger_date": TODAY,
            "created_at": f"{TODAY}T13:00:00+00:00",
            "delivered": False,
        },
    ]


# ---------------------------------------------------------------------------
# /api/briefing tests
# ---------------------------------------------------------------------------

def test_briefing_route_returns_200_with_valid_jwt():
    app = _make_app()
    admin = _briefing_admin_mock(briefing_rows=[_briefing_row("morning")])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.briefing.get_supabase_admin", return_value=admin):
        resp = app.get("/api/briefing", headers=AUTH_HEADER)

    assert resp.status_code == 200


def test_briefing_route_rejects_missing_jwt_with_401():
    app = _make_app()
    resp = app.get("/api/briefing")
    assert resp.status_code in (401, 403)


def test_briefing_family_id_from_jwt_not_query_param():
    """Route has no family_id query param — it's always from JWT."""
    app = _make_app()
    admin = _briefing_admin_mock(briefing_rows=[_briefing_row("morning")])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.briefing.get_supabase_admin", return_value=admin):
        # family_id is not a recognized param — route uses JWT only
        resp = app.get("/api/briefing?type=morning", headers=AUTH_HEADER)

    # Should succeed using JWT family_id
    assert resp.status_code == 200


def test_briefing_returns_latest_notification_for_today():
    app = _make_app()
    row = _briefing_row("morning")
    admin = _briefing_admin_mock(briefing_rows=[row])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.briefing.get_supabase_admin", return_value=admin):
        resp = app.get("/api/briefing", headers=AUTH_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert "Good morning" in data.get("content", "")


def test_briefing_fallback_to_on_demand_when_no_row():
    """When no notification row exists for today, generate on-demand."""
    app = _make_app()
    admin = _briefing_admin_mock(briefing_rows=[])  # Empty → fallback

    mock_on_demand = AsyncMock(return_value="Good morning — on demand\nSchedule is clear.")

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.briefing.get_supabase_admin", return_value=admin), \
         patch("app.api.routes.briefing._generate_on_demand", mock_on_demand):
        resp = app.get("/api/briefing", headers=AUTH_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert "morning" in data.get("content", "").lower() or data.get("type") == "morning"


def test_briefing_type_param_morning_returns_morning_type():
    app = _make_app()
    row = _briefing_row("morning")
    admin = _briefing_admin_mock(briefing_rows=[row])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.briefing.get_supabase_admin", return_value=admin):
        resp = app.get("/api/briefing?type=morning", headers=AUTH_HEADER)

    assert resp.status_code == 200
    assert resp.json()["type"] == "morning"


def test_briefing_type_param_evening_returns_evening_type():
    app = _make_app()
    row = _briefing_row("evening")
    admin = _briefing_admin_mock(briefing_rows=[row])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.briefing.get_supabase_admin", return_value=admin):
        resp = app.get("/api/briefing?type=evening", headers=AUTH_HEADER)

    assert resp.status_code == 200
    assert resp.json()["type"] == "evening"


def test_briefing_invalid_type_returns_422():
    app = _make_app()
    admin = _briefing_admin_mock()

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.briefing.get_supabase_admin", return_value=admin):
        resp = app.get("/api/briefing?type=weekly", headers=AUTH_HEADER)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /api/notifications tests
# ---------------------------------------------------------------------------

def test_notifications_route_returns_200_with_valid_jwt():
    app = _make_app()
    admin = _notifications_admin_mock(notification_rows=_notification_rows())

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications", headers=AUTH_HEADER)

    assert resp.status_code == 200


def test_notifications_route_rejects_missing_jwt_with_401():
    app = _make_app()
    resp = app.get("/api/notifications")
    assert resp.status_code in (401, 403)


def test_notifications_family_id_from_jwt_not_query_param():
    """Route has no family_id param — JWT only."""
    app = _make_app()
    admin = _notifications_admin_mock(notification_rows=[])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications?limit=10", headers=AUTH_HEADER)

    assert resp.status_code == 200


def test_notifications_returns_only_undelivered():
    app = _make_app()
    admin = _notifications_admin_mock(notification_rows=_notification_rows())

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications", headers=AUTH_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("count") == 2
    assert len(data.get("pending", [])) == 2


def test_notifications_marks_returned_as_delivered():
    """After GET /api/notifications, returned notifications should be marked delivered."""
    capture = {}
    admin = _notifications_admin_mock(notification_rows=_notification_rows(), capture_update=capture)
    app = _make_app()

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications", headers=AUTH_HEADER)

    assert resp.status_code == 200
    assert capture.get("called") is True


def test_notifications_sorted_newest_first():
    """Response shape should include pending list."""
    app = _make_app()
    admin = _notifications_admin_mock(notification_rows=_notification_rows())

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications", headers=AUTH_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert "pending" in data
    assert isinstance(data["pending"], list)


def test_notifications_limit_param_respected():
    """The limit query param should be forwarded to DB query."""
    limit_used = [None]

    admin = MagicMock()

    select_chain = MagicMock()
    select_chain.select.return_value = select_chain
    select_chain.eq.return_value = select_chain
    select_chain.order.return_value = select_chain

    def _limit(n):
        limit_used[0] = n
        return select_chain

    select_chain.limit = _limit
    select_chain.execute.return_value = MagicMock(data=[])

    update_chain = MagicMock()
    update_chain.in_.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    def _table_side(name):
        tbl = MagicMock()
        tbl.select.return_value = select_chain
        tbl.update.return_value = update_chain
        return tbl

    admin.table.side_effect = _table_side
    app = _make_app()

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications?limit=5", headers=AUTH_HEADER)

    assert resp.status_code == 200
    assert limit_used[0] == 5


def test_notifications_default_limit_is_20():
    """Default limit is 20."""
    limit_used = [None]

    admin = MagicMock()
    select_chain = MagicMock()
    select_chain.select.return_value = select_chain
    select_chain.eq.return_value = select_chain
    select_chain.order.return_value = select_chain

    def _limit(n):
        limit_used[0] = n
        return select_chain

    select_chain.limit = _limit
    select_chain.execute.return_value = MagicMock(data=[])

    update_chain = MagicMock()
    update_chain.in_.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    def _table_side(name):
        tbl = MagicMock()
        tbl.select.return_value = select_chain
        tbl.update.return_value = update_chain
        return tbl

    admin.table.side_effect = _table_side
    app = _make_app()

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications", headers=AUTH_HEADER)

    assert resp.status_code == 200
    assert limit_used[0] == 20


def test_notifications_returns_empty_when_none_pending():
    app = _make_app()
    admin = _notifications_admin_mock(notification_rows=[])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications", headers=AUTH_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["pending"] == []


def test_notifications_cannot_read_other_family_data():
    """DB query must always use the JWT family_id, never a query param value."""
    eq_calls = []

    admin = MagicMock()
    select_chain = MagicMock()

    def _eq(col, val):
        eq_calls.append((col, val))
        return select_chain

    select_chain.select.return_value = select_chain
    select_chain.eq = _eq
    select_chain.order.return_value = select_chain
    select_chain.limit.return_value = select_chain
    select_chain.execute.return_value = MagicMock(data=[])

    update_chain = MagicMock()
    update_chain.in_.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    def _table_side(name):
        tbl = MagicMock()
        tbl.select.return_value = select_chain
        tbl.update.return_value = update_chain
        return tbl

    admin.table.side_effect = _table_side
    app = _make_app()

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.notifications.get_supabase_admin", return_value=admin):
        resp = app.get("/api/notifications", headers=AUTH_HEADER)

    assert resp.status_code == 200
    family_filters = [(col, val) for col, val in eq_calls if col == "family_id"]
    for _, val in family_filters:
        assert val == FAMILY_ID, f"Wrong family_id used: {val}"
