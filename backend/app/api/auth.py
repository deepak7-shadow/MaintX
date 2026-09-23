"""
Authentication routes.

Endpoints
---------
GET  /api/auth/me       — Return the current authenticated user's profile.
POST /api/auth/logout   — Invalidate the Supabase session server-side.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_current_user
from app.core.security import decode_supabase_jwt, extract_user_id
from app.db.client import get_supabase_client
from app.schemas.auth import UserProfileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

_bearer = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current authenticated user",
    description=(
        "Validates the Supabase JWT in the Authorization header and returns "
        "the authenticated user's profile. "
        "**Role is always sourced from the database — never from the token.**"
    ),
)
async def get_me(
    current_user: UserProfileResponse = Depends(get_current_user),
) -> UserProfileResponse:
    """Return the authenticated user's profile (id, email, name, role)."""
    return current_user


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    summary="Logout — invalidate the current session",
    description=(
        "Signs the user out of Supabase, invalidating the refresh token. "
        "The client should also clear any stored tokens."
    ),
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Server-side logout: sign the user out via the Supabase admin API so that
    their refresh token is revoked even if the access token hasn't expired.
    """
    token = credentials.credentials

    # Verify the JWT first (confirm the caller is the actual user)
    payload = decode_supabase_jwt(token)
    user_id = extract_user_id(payload)

    client = get_supabase_client()
    try:
        # admin.sign_out revokes the user's refresh tokens
        client.auth.admin.sign_out(user_id)
        logger.info("User %s signed out successfully.", user_id)
    except Exception as exc:
        logger.error("Sign-out failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Sign-out request to authentication provider failed.",
        ) from exc

    return {"success": True, "message": "Signed out successfully."}
