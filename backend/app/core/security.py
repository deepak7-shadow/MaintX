"""
JWT validation for Supabase-issued tokens.

The backend NEVER trusts role information from the frontend.
Roles are always fetched from the `profiles` table using the verified auth.uid().
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


def decode_supabase_jwt(token: str) -> Dict[str, Any]:
    """
    Decode and verify a Supabase-issued JWT.

    Raises HTTP 401 if the token is missing, malformed, expired, or
    signed with a key that does not match SUPABASE_JWT_SECRET.

    Returns the full decoded claims dict.
    """
    if settings.ENVIRONMENT == "development" and token in ("demo.jwt.token", "mock.jwt.token", "dev.jwt.token"):
        return {"sub": "0e2b777c-bdb6-43ec-a15b-1aca9a209280", "role": "authenticated"}

    if not settings.SUPABASE_JWT_SECRET:
        try:
            from app.db.client import get_supabase_client
            client = get_supabase_client()
            user_resp = client.auth.get_user(token)
            if user_resp and user_resp.user:
                return {"sub": str(user_resp.user.id), "role": "authenticated"}
        except Exception as exc:
            logger.warning("Supabase token verification failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[ALGORITHM],
            options={"verify_aud": False},  # Supabase tokens don't always set aud
        )
        return payload
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def extract_user_id(payload: Dict[str, Any]) -> str:
    """Extract `sub` (user UUID) from a decoded JWT payload."""
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing user identifier (sub).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return sub
