"""Supabase authentication utilities for token refresh and session management."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SupabaseAuthError(Exception):
    """Raised when Supabase authentication operations fail."""
    pass


async def refresh_access_token(refresh_token: str) -> Tuple[str, str, datetime]:
    """Refresh Supabase access token using refresh token.

    Args:
        refresh_token: The refresh token from previous authentication

    Returns:
        Tuple of (new_access_token, new_refresh_token, token_expires_at)

    Raises:
        SupabaseAuthError: If token refresh fails
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise SupabaseAuthError("Supabase not configured")

    token_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=refresh_token"

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                token_url,
                json=payload,
                headers={
                    "apikey": settings.SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed ({response.status_code}): {response.text}")
                raise SupabaseAuthError(f"Token refresh failed: {response.status_code}")

            token_data = response.json()
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token", refresh_token)

            if not new_access_token:
                raise SupabaseAuthError("No access token in refresh response")

            # Assume 1 hour expiration (standard Supabase default)
            token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            logger.info("Token successfully refreshed")
            return new_access_token, new_refresh_token, token_expires_at

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Supabase token endpoint: {str(e)}")
        raise SupabaseAuthError(f"Connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise SupabaseAuthError(f"Token refresh failed: {str(e)}")


def should_refresh_token(token_expires_at: datetime) -> bool:
    """Check if token should be proactively refreshed.

    Refreshes if token will expire within the next 5 minutes.

    Args:
        token_expires_at: When the token expires

    Returns:
        True if token should be refreshed, False otherwise
    """
    if not token_expires_at:
        return False

    # Refresh if expiration is within 5 minutes
    time_until_expiry = token_expires_at - datetime.now(timezone.utc)
    return time_until_expiry < timedelta(minutes=5)


async def revoke_session() -> None:
    """Revoke the current session on Supabase auth server.

    This is called on logout to invalidate the session server-side.
    Currently a no-op as Supabase doesn't require explicit revocation
    for access tokens (they expire naturally).

    Raises:
        SupabaseAuthError: If revocation fails
    """
    # Supabase tokens expire naturally; explicit revocation not required
    # This function exists for future extension and explicit cleanup if needed
    pass
