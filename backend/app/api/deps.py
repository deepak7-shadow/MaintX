"""
FastAPI dependency functions for authentication and role-based access control.

Usage
-----
    # Any authenticated user
    user = Depends(get_current_user)

    # Specific role guard
    user = Depends(require_role(UserRole.ADMIN))

    # Convenience shorthands
    user = Depends(require_admin)
    user = Depends(require_supervisor)
    user = Depends(require_engineer)
    user = Depends(require_security_analyst)
    user = Depends(require_auditor)
"""
from __future__ import annotations

from typing import Callable, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_supabase_jwt, extract_user_id
from app.schemas.auth import UserProfileResponse, UserRole
from app.services.auth_service import get_profile_by_user_id

# Bearer token extractor — auto_error=True raises 401 when header is missing
_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UserProfileResponse:
    """
    Validate the Bearer JWT and return the authenticated user profile.

    Role is fetched from the database — never trusted from the JWT.
    """
    token = credentials.credentials
    payload = decode_supabase_jwt(token)
    user_id = extract_user_id(payload)
    return await get_profile_by_user_id(user_id)


def require_role(*allowed_roles: UserRole) -> Callable:
    """
    Return a FastAPI dependency that raises HTTP 403 if the authenticated
    user's role is not in `allowed_roles`.
    """
    role_set: Set[UserRole] = set(allowed_roles)

    async def _dependency(
        current_user: UserProfileResponse = Depends(get_current_user),
    ) -> UserProfileResponse:
        if current_user.role not in role_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This action requires one of the following roles: "
                    f"{[r.value for r in role_set]}. "
                    f"Your role is '{current_user.role.value}'."
                ),
            )
        return current_user

    return _dependency


# ---------------------------------------------------------------------------
# Convenience role guards
# ---------------------------------------------------------------------------

require_admin = require_role(UserRole.ADMIN)
"""Only ADMIN may proceed."""

require_supervisor = require_role(UserRole.SUPERVISOR, UserRole.ADMIN)
"""SUPERVISOR or ADMIN may proceed (admin is always a superset)."""

require_engineer = require_role(
    UserRole.MAINTENANCE_ENGINEER, UserRole.SUPERVISOR, UserRole.ADMIN
)
"""MAINTENANCE_ENGINEER, SUPERVISOR, or ADMIN."""

require_security_analyst = require_role(
    UserRole.SECURITY_ANALYST, UserRole.ADMIN
)
"""SECURITY_ANALYST or ADMIN."""

require_auditor = require_role(
    UserRole.AUDITOR,
    UserRole.ADMIN,
    UserRole.SUPERVISOR,
    UserRole.SECURITY_ANALYST,
)
"""Read-only audit access; AUDITOR, SUPERVISOR, SECURITY_ANALYST, or ADMIN."""
