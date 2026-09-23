"""
Stage 3 auth tests — role-based access control.

These are unit tests that verify:
    1. GET /api/auth/me returns user data for a valid token.
    2. A request without a token gets HTTP 401/403.
    3. A MAINTENANCE_ENGINEER cannot access supervisor-only actions.
    4. An AUDITOR cannot modify data.
    5. A SUPERVISOR can approve maintenance.
    6. An ADMIN has full access.
    7. A SECURITY_ANALYST can access security-related read endpoints.

JWT decode and profile fetch are mocked so no real Supabase calls are made.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.auth import UserProfileResponse, UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(role: UserRole) -> UserProfileResponse:
    return UserProfileResponse(
        id="00000000-0000-0000-0000-000000000001",
        email=f"{role.value.lower()}@maintx.test",
        name=f"Test {role.value}",
        role=role,
        department="Test Dept",
        engineer_code=None,
    )


DUMMY_JWT_PAYLOAD = {
    "sub": "00000000-0000-0000-0000-000000000001",
    "email": "test@maintx.test",
    "role": "authenticated",
    "aud": "authenticated",
}

_MOCK_TOKEN = "mock.jwt.token"
_AUTH_HEADER = {"Authorization": f"Bearer {_MOCK_TOKEN}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@contextmanager
def _patch_auth(role: UserRole):
    """
    Patch the full decode_supabase_jwt function (bypassing the JWT secret check)
    and patch get_profile_by_user_id at the point it's called in deps.
    """
    profile = _make_profile(role)
    # Patch decode_supabase_jwt where deps.py holds its reference (imported name)
    # and patch get_profile_by_user_id at the deps import point.
    with patch(
        "app.api.deps.decode_supabase_jwt",
        return_value=DUMMY_JWT_PAYLOAD,
    ):
        with patch(
            "app.api.deps.get_profile_by_user_id",
            new=AsyncMock(return_value=profile),
        ):
            yield profile


def _remove_test_route(path: str):
    app.routes[:] = [
        r for r in app.routes
        if not (isinstance(r, APIRoute) and r.path == path)
    ]


# ---------------------------------------------------------------------------
# 1. Health check (unauthenticated)
# ---------------------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# 2. GET /api/auth/me
# ---------------------------------------------------------------------------


def test_me_requires_token(client):
    """Request without Authorization header → 401 or 403."""
    r = client.get("/api/auth/me")
    assert r.status_code in (401, 403)


def test_me_returns_profile_for_engineer(client):
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        r = client.get("/api/auth/me", headers=_AUTH_HEADER)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "MAINTENANCE_ENGINEER"


def test_me_returns_profile_for_admin(client):
    with _patch_auth(UserRole.ADMIN):
        r = client.get("/api/auth/me", headers=_AUTH_HEADER)
    assert r.status_code == 200
    assert r.json()["role"] == "ADMIN"


# ---------------------------------------------------------------------------
# 3. Role-based access: engineer cannot access supervisor-only action
# ---------------------------------------------------------------------------


def test_engineer_cannot_approve_maintenance(client):
    """An MAINTENANCE_ENGINEER should receive HTTP 403 on supervisor endpoints."""
    from app.api.deps import require_supervisor

    @app.get("/api/test/supervisor-action", include_in_schema=False)
    async def _supervisor_action(user=Depends(require_supervisor)):
        return {"ok": True}

    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        r = client.get("/api/test/supervisor-action", headers=_AUTH_HEADER)

    _remove_test_route("/api/test/supervisor-action")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 4. Auditor cannot modify data
# ---------------------------------------------------------------------------


def test_auditor_cannot_modify_data(client):
    """An AUDITOR hitting an engineer-required write endpoint gets HTTP 403."""
    from app.api.deps import require_engineer

    @app.post("/api/test/engineer-write", include_in_schema=False)
    async def _engineer_write(user=Depends(require_engineer)):
        return {"ok": True}

    with _patch_auth(UserRole.AUDITOR):
        r = client.post("/api/test/engineer-write", headers=_AUTH_HEADER)

    _remove_test_route("/api/test/engineer-write")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 5. Supervisor can approve maintenance
# ---------------------------------------------------------------------------


def test_supervisor_can_approve_maintenance(client):
    """A SUPERVISOR can access supervisor-required endpoints."""
    from app.api.deps import require_supervisor

    @app.post("/api/test/approve", include_in_schema=False)
    async def _approve(user=Depends(require_supervisor)):
        return {"approved": True, "by": user.role.value}

    with _patch_auth(UserRole.SUPERVISOR):
        r = client.post("/api/test/approve", headers=_AUTH_HEADER)

    _remove_test_route("/api/test/approve")
    assert r.status_code == 200
    assert r.json()["approved"] is True
    assert r.json()["by"] == "SUPERVISOR"


# ---------------------------------------------------------------------------
# 6. Admin has access to all role-guarded endpoints
# ---------------------------------------------------------------------------


def test_admin_can_access_supervisor_action(client):
    from app.api.deps import require_supervisor

    @app.get("/api/test/admin-supervisor-access", include_in_schema=False)
    async def _admin_sup(user=Depends(require_supervisor)):
        return {"role": user.role.value}

    with _patch_auth(UserRole.ADMIN):
        r = client.get("/api/test/admin-supervisor-access", headers=_AUTH_HEADER)

    _remove_test_route("/api/test/admin-supervisor-access")
    assert r.status_code == 200
    assert r.json()["role"] == "ADMIN"


def test_admin_can_access_engineer_write(client):
    from app.api.deps import require_engineer

    @app.post("/api/test/admin-engineer-write", include_in_schema=False)
    async def _admin_eng(user=Depends(require_engineer)):
        return {"role": user.role.value}

    with _patch_auth(UserRole.ADMIN):
        r = client.post("/api/test/admin-engineer-write", headers=_AUTH_HEADER)

    _remove_test_route("/api/test/admin-engineer-write")
    assert r.status_code == 200
    assert r.json()["role"] == "ADMIN"


# ---------------------------------------------------------------------------
# 7. Security analyst gets appropriate access
# ---------------------------------------------------------------------------


def test_security_analyst_read_access(client):
    from app.api.deps import require_security_analyst

    @app.get("/api/test/security-read", include_in_schema=False)
    async def _sec_read(user=Depends(require_security_analyst)):
        return {"role": user.role.value}

    with _patch_auth(UserRole.SECURITY_ANALYST):
        r = client.get("/api/test/security-read", headers=_AUTH_HEADER)

    _remove_test_route("/api/test/security-read")
    assert r.status_code == 200
    assert r.json()["role"] == "SECURITY_ANALYST"
