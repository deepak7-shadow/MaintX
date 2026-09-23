"""
Supabase client singleton — shared across the application.

We use the *service-role* key on the backend so that:
  - We can read the `profiles` table regardless of RLS policies.
  - We NEVER expose the service key to the frontend.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Return the shared Supabase admin client (service-role key).

    Uses `lru_cache` so that the client is instantiated only once and
    reused across all requests.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SECRET_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SECRET_KEY must be set in environment."
        )
    logger.info("Initialising Supabase admin client for %s", settings.SUPABASE_URL)
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
