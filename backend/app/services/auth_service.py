"""
Auth service — fetches and validates user profile from the database.

Role is ALWAYS sourced from the `profiles` table (never from the JWT or
any client-supplied value).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, status

from app.db.client import get_supabase_client
from app.schemas.auth import UserProfileResponse, UserRole

logger = logging.getLogger(__name__)


async def get_profile_by_user_id(user_id: str) -> UserProfileResponse:
    """
    Fetch the user profile row from `public.profiles` for the given Supabase
    auth user ID.

    Raises:
        HTTP 404  — if the user has no profile (e.g. auth user exists but
                    the trigger hasn't run yet or was skipped).
        HTTP 403  — if the account is deactivated.
    """
    client = get_supabase_client()

    try:
        result = (
            client.table("profiles")
            .select("id, email, full_name, role, department, engineer_code, is_active")
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.error("Supabase profiles query failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve user profile. Please try again later.",
        ) from exc

    if not result.data:
        logger.warning("No profile found for auth user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found. Contact an administrator.",
        )

    row = result.data

    # Enforce account active status
    if not row.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    # Validate that the stored role is one we recognise
    try:
        role = UserRole(row["role"])
    except ValueError:
        logger.error(
            "Unknown role '%s' for user %s — denying access.", row.get("role"), user_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has an unrecognised role. Contact an administrator.",
        )

    return UserProfileResponse(
        id=row["id"],
        email=row["email"],
        name=row.get("full_name"),
        role=role,
        department=row.get("department"),
        engineer_code=row.get("engineer_code"),
    )
