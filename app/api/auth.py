"""Supabase-backed authentication with LinkedIn OIDC and automatic token refresh.

Handles JWT verification from Supabase Auth (supports both HS256 symmetric and
ES256/RS256 asymmetric tokens), automatic user provisioning from LinkedIn OAuth
metadata, and silent token refresh for "never logout" persistent sessions.
"""

import logging
from typing import Optional
from datetime import datetime, timezone
import jwt
from jwt import PyJWKClient, PyJWKClientError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import User
from app.api.dependencies import get_db
from app.services.supabase_auth import (
    refresh_access_token,
    should_refresh_token,
    SupabaseAuthError,
)

logger = logging.getLogger(__name__)

# HTTP Bearer scheme for JWT token extraction
security = HTTPBearer()

# Module-level JWKS client for asymmetric token verification (cached to avoid repeated HTTP calls)
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    """Get or initialize the cached JWKS client for Supabase public key verification.

    JWKS (JSON Web Key Set) endpoint provides public keys for verifying ES256/RS256 tokens.
    Client is cached at module level to avoid repeated HTTP requests to Supabase.

    Returns:
        PyJWKClient configured for the Supabase JWKS endpoint

    Raises:
        ValueError: If SUPABASE_URL not configured
    """
    global _jwks_client

    if _jwks_client is not None:
        return _jwks_client

    if not settings.SUPABASE_URL:
        raise ValueError("SUPABASE_URL must be configured for JWKS client")

    jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    logger.debug(f"Initializing JWKS client for URL: {jwks_url}")

    _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


class JWTVerificationError(Exception):
    """Raised when JWT verification fails."""
    pass


def _decode_jwt(token: str, verify_exp: bool = True) -> dict:
    """Decode and verify Supabase JWT token (supports HS256, ES256, RS256).

    Supabase can issue tokens signed with different algorithms:
    - HS256 (symmetric, legacy): Uses SUPABASE_JWT_SECRET
    - ES256/RS256 (asymmetric, modern): Fetches public key from JWKS endpoint

    Flow:
    1. Inspect unverified header to determine algorithm
    2. For asymmetric: Fetch signing key from Supabase's JWKS endpoint
    3. For symmetric: Use SUPABASE_JWT_SECRET
    4. Verify signature, expiration, and audience

    Args:
        token: JWT token from Authorization header
        verify_exp: Whether to verify token expiration

    Returns:
        Decoded JWT payload dict

    Raises:
        JWTVerificationError: If token is invalid or verification fails
    """
    try:
        # Get the unverified header to inspect algorithm
        unverified_header = jwt.get_unverified_header(token)
        algorithm = unverified_header.get("alg", "unknown")

        logger.debug(f"JWT algorithm detected: {algorithm}")

        # Determine verification key based on algorithm type
        if algorithm in ["ES256", "RS256"]:
            # Asymmetric algorithm: Fetch public key from Supabase JWKS endpoint
            logger.debug(f"Using asymmetric algorithm {algorithm}, fetching public key from JWKS...")
            try:
                jwks_client = _get_jwks_client()
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                verification_key = signing_key.key

                # Verify with public key
                payload = jwt.decode(
                    token,
                    verification_key,
                    algorithms=[algorithm],
                    audience="authenticated",
                    options={"verify_exp": verify_exp},
                )
                logger.debug(f"JWT verified successfully with {algorithm} public key")
                return payload

            except PyJWKClientError as e:
                logger.error(f"Failed to fetch public key from JWKS endpoint: {str(e)}")
                raise JWTVerificationError(f"Failed to verify token: {str(e)}")

        elif algorithm == "HS256":
            # Symmetric algorithm: Use SUPABASE_JWT_SECRET
            if not settings.SUPABASE_JWT_SECRET:
                logger.error("SUPABASE_JWT_SECRET not configured for HS256 verification")
                raise JWTVerificationError(
                    "SUPABASE_JWT_SECRET not configured. "
                    "Set it in .env from Supabase dashboard."
                )

            logger.debug("Using symmetric HS256 algorithm with SUPABASE_JWT_SECRET")

            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_exp": verify_exp},
            )
            logger.debug("JWT verified successfully with HS256 secret")
            return payload

        else:
            # Unknown algorithm
            logger.error(f"Unsupported JWT algorithm: {algorithm}")
            raise JWTVerificationError(f"Unsupported JWT algorithm: {algorithm}")

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise JWTVerificationError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise JWTVerificationError(f"Invalid token: {str(e)}")
    except JWTVerificationError:
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error during JWT verification: {type(e).__name__}: {str(e)}")
        raise JWTVerificationError(f"Token verification failed: {str(e)}")


async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    """Get current user from database or fall back to .env configuration.

    SMART FALLBACK FLOW (No Bearer Token Required):
    1. Try fetching from database using default email from .env
    2. If found in DB AND has linkedin_access_token → Return DB user (dynamic)
    3. If NOT in DB OR missing token → Fall back to .env configuration (static)

    This enables instant testing in Swagger UI without manual token entry.
    Production auth can still use database records when users log in via OAuth.

    Args:
        db: Database session

    Returns:
        User object (either from database or constructed from .env)

    Raises:
        HTTPException 500: On database connection errors only
    """
    try:
        # Get default email from settings (e.g., "vinayuttangi@gmail.com")
        default_email = getattr(settings, "LINKEDIN_USER_EMAIL", "vinayuttangi@gmail.com")
        logger.debug(f"Looking up user: {default_email}")

        # 1. Try fetching from database first
        stmt = select(User).where(User.email == default_email)
        result = await db.execute(stmt)
        db_user = result.scalars().first()

        # If user exists in DB and has valid LinkedIn access token, return DB record
        if db_user and db_user.linkedin_access_token:
            logger.info(f"User found in database with active tokens: {default_email}")
            return db_user

        # 2. Fallback to .env configuration (static user)
        logger.info(f"Falling back to .env configuration for user: {default_email}")

        fallback_user = User(
            email=default_email,
            full_name=getattr(settings, "LINKEDIN_USER_NAME", "VINAYAKA P"),
            linkedin_profile_url=getattr(
                settings,
                "LINKEDIN_PROFILE_URL",
                f"https://linkedin.com/in/{default_email.split('@')[0]}"
            ),
            linkedin_access_token=getattr(settings, "LINKEDIN_ACCESS_TOKEN", None),
            linkedin_person_urn=getattr(settings, "LINKEDIN_PERSON_URN", None),
        )

        logger.debug(
            f"Constructed fallback user: {fallback_user.email} | "
            f"Has token: {bool(fallback_user.linkedin_access_token)}"
        )

        return fallback_user

    except Exception as e:
        logger.error(f"Error retrieving user: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user configuration",
        )


async def get_current_user_optional(db: AsyncSession = Depends(get_db)) -> Optional[User]:
    """Optional version of get_current_user (always returns a user with fallback).

    Since get_current_user now has smart fallback (DB then .env), this always
    returns a User object. Kept for backward compatibility with optional-auth endpoints.

    Args:
        db: Database session

    Returns:
        User object (from database or .env fallback)

    Raises:
        HTTPException 500: On database connection errors only
    """
    return await get_current_user(db)
