"""Supabase-backed authentication with LinkedIn OAuth2.

Handles JWT verification from Supabase Auth and automatic user provisioning
from LinkedIn OAuth metadata. Integrates with the User model for tracking.
"""

import logging
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import User
from app.api.dependencies import get_db

logger = logging.getLogger(__name__)

# HTTP Bearer scheme for JWT token extraction
security = HTTPBearer()


class JWTVerificationError(Exception):
    """Raised when JWT verification fails."""
    pass


def _decode_jwt(token: str) -> dict:
    """Decode and verify Supabase JWT token.

    Args:
        token: JWT token from Authorization header

    Returns:
        Decoded JWT payload dict

    Raises:
        JWTVerificationError: If token is invalid or verification fails
    """
    if not settings.SUPABASE_JWT_SECRET:
        raise JWTVerificationError(
            "SUPABASE_JWT_SECRET not configured. "
            "Set it in .env from Supabase dashboard."
        )

    try:
        # Decode with Supabase settings:
        # - Algorithm: HS256 (HMAC with SHA-256)
        # - Audience: "authenticated" (standard Supabase audience)
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise JWTVerificationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise JWTVerificationError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise JWTVerificationError(f"Token verification failed: {str(e)}")


async def get_current_user(
    credentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency to get the current authenticated user.

    Flow:
    1. Extract JWT from Authorization header (Bearer token)
    2. Verify and decode JWT using Supabase secret
    3. Extract email and LinkedIn URL from token payload
    4. Query database for existing user
    5. If not found, auto-create user from JWT metadata
    6. Return User object

    Args:
        credentials: HTTP Bearer credentials from request header
        db: Database session

    Returns:
        User object (either from database or newly created)

    Raises:
        HTTPException 401: If token is invalid or verification fails
        HTTPException 400: If email is not in token payload
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Decode JWT
    try:
        payload = _decode_jwt(token)
    except JWTVerificationError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract email (required)
    email = payload.get("email")
    if not email:
        logger.error("Email not found in JWT payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found in token",
        )

    # Extract LinkedIn URL from user_metadata (optional)
    user_metadata = payload.get("user_metadata", {})
    linkedin_url = user_metadata.get("linkedin_profile_url", "")

    logger.info(f"Authenticated user: {email}")

    # Query for existing user
    try:
        stmt = select(User).where(User.email == email)
        existing_user = (await db.execute(stmt)).scalars().first()

        if existing_user:
            logger.debug(f"User found in database: {existing_user.user_id}")
            return existing_user

        # User not found - auto-create from JWT metadata
        logger.info(f"Auto-creating user from JWT: {email}")
        new_user = User(
            email=email,
            linkedin_profile_url=linkedin_url or f"https://linkedin.com/in/{email.split('@')[0]}",
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        logger.info(f"User auto-created: {new_user.user_id} ({email})")
        return new_user

    except Exception as e:
        logger.error(f"Database error during user lookup/creation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to authenticate user",
        )


async def get_current_user_optional(
    credentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Optional version of get_current_user.

    Returns None if no credentials provided (for public endpoints).
    Raises 401 if credentials are provided but invalid.

    Args:
        credentials: HTTP Bearer credentials (optional)
        db: Database session

    Returns:
        User object or None if unauthenticated

    Raises:
        HTTPException 401: If token is provided but invalid
    """
    if not credentials:
        return None

    return await get_current_user(credentials, db)
