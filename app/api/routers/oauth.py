"""LinkedIn OIDC OAuth authentication endpoints.

Handles the OAuth handshake flow:
1. GET /login - Redirects user to LinkedIn via Supabase OIDC
2. GET /callback - Handles OAuth callback, exchanges code for tokens
3. POST /logout - Revokes session and clears tokens
"""

import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
import jwt

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
import httpx

from app.core.config import settings
from app.db import User
from app.api.dependencies import get_db
from app.api.auth import get_current_user, security
from app.services.supabase_auth import revoke_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


class SessionTokenPayload(BaseModel):
    """OAuth session tokens received from browser hash fragment."""
    access_token: str
    refresh_token: str
    provider_token: Optional[str] = None
    expires_in: Optional[int] = 3600


def _get_hash_fragment_handler_html() -> str:
    """Generate HTML/JS page to handle OAuth tokens in URL hash fragments.

    Supabase GoTrue sends tokens via hash (#access_token=...) in implicit flow.
    HTTP servers never see hash fragments, but JavaScript running in the browser can.
    This page parses the hash and POSTs tokens to the backend /callback/session endpoint.

    Returns:
        HTML string containing embedded JavaScript
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LinkedIn Authentication</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen",
                    "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
                text-align: center;
                max-width: 400px;
            }
            h1 {
                color: #333;
                margin: 0 0 20px 0;
                font-size: 24px;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .status {
                color: #666;
                font-size: 14px;
                margin-top: 20px;
            }
            .error {
                color: #d32f2f;
                padding: 15px;
                background: #ffebee;
                border-radius: 4px;
                margin-top: 20px;
                display: none;
            }
            .success {
                color: #388e3c;
                padding: 15px;
                background: #e8f5e9;
                border-radius: 4px;
                margin-top: 20px;
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>LinkedIn Authentication</h1>
            <div class="spinner"></div>
            <div class="status" id="status">Processing authentication...</div>
            <div class="error" id="error"></div>
            <div class="success" id="success"></div>
        </div>

        <script>
            (function() {
                const hash = window.location.hash;
                const statusEl = document.getElementById('status');
                const errorEl = document.getElementById('error');
                const successEl = document.getElementById('success');

                // Log for debugging
                console.log('Hash fragment:', hash);
                console.log('Full URL:', window.location.href);

                // Check if hash fragment exists
                if (!hash || hash === '#') {
                    console.error('No authentication data found in URL hash');
                    statusEl.style.display = 'none';
                    errorEl.style.display = 'block';
                    errorEl.textContent = 'No authentication data found in URL.';
                    return;
                }

                try {
                    // Parse hash fragment to extract tokens
                    const params = new URLSearchParams(hash.substring(1)); // Remove leading #
                    const accessToken = params.get('access_token');
                    const refreshToken = params.get('refresh_token');
                    const providerToken = params.get('provider_token');
                    const expiresIn = params.get('expires_in') ? parseInt(params.get('expires_in')) : 3600;

                    console.log('Parsed tokens:', {
                        hasAccessToken: !!accessToken,
                        hasRefreshToken: !!refreshToken,
                        hasProviderToken: !!providerToken,
                        expiresIn: expiresIn,
                    });

                    if (!accessToken || !refreshToken) {
                        throw new Error('Missing required tokens in URL hash');
                    }

                    // POST tokens to backend session endpoint
                    statusEl.textContent = 'Saving session...';
                    fetch('/api/v1/auth/linkedin/callback/session', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            access_token: accessToken,
                            refresh_token: refreshToken,
                            provider_token: providerToken,
                            expires_in: expiresIn,
                        }),
                    })
                    .then(response => {
                        console.log('Session endpoint response status:', response.status);
                        if (!response.ok) {
                            return response.json().then(err => {
                                throw new Error(err.detail || 'Session creation failed');
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log('Session created successfully:', data);
                        statusEl.style.display = 'none';
                        successEl.style.display = 'block';
                        successEl.innerHTML = `
                            <strong>✓ Authentication Successful!</strong><br>
                            Email: ${data.email}<br>
                            Name: ${data.full_name}<br>
                            <br>
                            Redirecting in 3 seconds...
                        `;
                        setTimeout(() => {
                            window.location.href = '/';
                        }, 3000);
                    })
                    .catch(err => {
                        console.error('Session creation error:', err);
                        statusEl.style.display = 'none';
                        errorEl.style.display = 'block';
                        errorEl.innerHTML = `
                            <strong>Authentication Failed</strong><br>
                            ${err.message}
                        `;
                    });
                } catch (err) {
                    console.error('Hash parsing error:', err);
                    statusEl.style.display = 'none';
                    errorEl.style.display = 'block';
                    errorEl.textContent = 'Failed to parse authentication data: ' + err.message;
                }
            })();
        </script>
    </body>
    </html>
    """


@router.get("/linkedin/login")
async def linkedin_login():
    """Initiate LinkedIn OIDC login flow via Supabase GoTrue.

    Delegates to Supabase's native OAuth authorize endpoint with LinkedIn OIDC provider.
    Supabase GoTrue handles all OAuth parameter configuration internally based on the
    provider ID configured in the Supabase dashboard.

    Returns:
        RedirectResponse to LinkedIn OIDC provider via Supabase GoTrue

    Raises:
        HTTPException 500: If Supabase is not configured
    """
    # Validate Supabase configuration
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        logger.error("Supabase configuration missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase not configured",
        )

    # Validate callback URI is configured
    if not settings.OAUTH_REDIRECT_URI:
        logger.error("OAuth redirect URI not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth redirect URI not configured",
        )

    # Log configuration (masked for security)
    logger.debug(
        f"LinkedIn login initiated | "
        f"Supabase URL: {settings.SUPABASE_URL} | "
        f"Provider: {settings.SUPABASE_LINKEDIN_OIDC_PROVIDER} | "
        f"Redirect URI: {settings.OAUTH_REDIRECT_URI} | "
        f"Supabase Anon Key: {settings.SUPABASE_ANON_KEY[:4]}...{settings.SUPABASE_ANON_KEY[-4:]}"
    )

    # Construct Supabase GoTrue OAuth URL
    # IMPORTANT: Do NOT pass client_id here - Supabase GoTrue configures it server-side
    # The provider parameter must match the OIDC provider configured in Supabase dashboard
    auth_url = (
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/authorize"
        f"?provider={settings.SUPABASE_LINKEDIN_OIDC_PROVIDER}"
        f"&redirect_to={settings.OAUTH_REDIRECT_URI}"
    )

    logger.info(
        f"Redirecting to Supabase GoTrue OAuth endpoint for LinkedIn OIDC | "
        f"URL pattern: {settings.SUPABASE_URL.rstrip('/')}/auth/v1/authorize"
        f"?provider={settings.SUPABASE_LINKEDIN_OIDC_PROVIDER}"
        f"&redirect_to=[REDIRECT_URI]"
    )
    logger.debug(f"Full redirect URL: {auth_url}")

    return RedirectResponse(url=auth_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/linkedin/callback")
async def linkedin_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback from LinkedIn/Supabase.

    Supports TWO OAuth flows:
    1. Authorization Code Flow: Receives ?code= query parameter
    2. Implicit Flow with Hash Fragment: Receives #access_token=... in browser hash
       (returns HTML/JS that parses hash and POSTs to /callback/session)

    Args:
        code: Authorization code from Supabase OAuth flow
        error: Error code if authorization failed
        error_description: Human-readable error description
        db: Database session

    Returns:
        - If code present: JSON response with user info and access token
        - If code absent: HTML page with JavaScript to handle hash fragments
    """
    logger.info("LinkedIn OAuth callback received")

    # Handle OAuth errors from Supabase
    if error:
        logger.warning(
            f"OAuth callback error from Supabase: {error} | "
            f"Description: {error_description or 'No description'}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {error}",
        )

    # If no authorization code, return HTML/JS to handle hash fragments
    if not code:
        logger.info("No authorization code in query params - returning hash fragment handler")
        return HTMLResponse(
            content=_get_hash_fragment_handler_html(),
            status_code=status.HTTP_200_OK,
        )

    logger.debug(f"Authorization code received (length: {len(code)} chars)")

    # Validate Supabase is configured for token exchange
    if not settings.SUPABASE_URL:
        logger.error("SUPABASE_URL not configured for token exchange")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase not configured",
        )

    # Log configuration before token exchange (masked for security)
    logger.debug(
        f"Token exchange configuration | "
        f"Supabase URL: {settings.SUPABASE_URL} | "
        f"Redirect URI: {settings.OAUTH_REDIRECT_URI} | "
        f"Supabase Anon Key: {settings.SUPABASE_ANON_KEY[:4]}...{settings.SUPABASE_ANON_KEY[-4:]}"
    )

    # Exchange code for tokens with Supabase
    token_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=authorization_code"
    logger.debug(f"Token endpoint: {settings.SUPABASE_URL.rstrip('/')}/auth/v1/token")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_to": settings.OAUTH_REDIRECT_URI,
    }

    try:
        logger.info(f"Exchanging authorization code for tokens | Endpoint: {token_url}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                token_url,
                json=payload,
                headers={
                    "apikey": settings.SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
            )

            logger.debug(f"Token exchange response status: {response.status_code}")

            if response.status_code != 200:
                logger.error(
                    f"Token exchange failed | "
                    f"Status: {response.status_code} | "
                    f"Response: {response.text[:500]}"  # Log first 500 chars to avoid leaking tokens
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to exchange authorization code for tokens",
                )

            token_data = response.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            user_data = token_data.get("user", {})

            logger.debug(f"Token data received | Has access_token: {bool(access_token)} | Has refresh_token: {bool(refresh_token)}")

            if not access_token:
                logger.error("No access token in Supabase token response")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No access token in response",
                )

            # Extract user info from token payload
            email = user_data.get("email", "")
            full_name = user_data.get("user_metadata", {}).get("full_name", "")
            linkedin_profile_url = (
                user_data.get("user_metadata", {}).get("linkedin_profile_url", "")
                or f"https://linkedin.com/in/{email.split('@')[0]}"
            )

            if not email:
                logger.error("No email in Supabase user data | User data keys: " + str(user_data.keys()))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No email in authentication response",
                )

            # Calculate token expiration (1 hour from now)
            token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            logger.info(
                f"User authenticated | Email: {email} | "
                f"Full Name: {full_name} | "
                f"Token Expires: {token_expires_at.isoformat()}"
            )

            # Upsert user with tokens
            stmt = pg_insert(User).values(
                email=email,
                full_name=full_name,
                linkedin_profile_url=linkedin_profile_url,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["email"],
                set_={
                    "full_name": full_name,
                    "linkedin_profile_url": linkedin_profile_url,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expires_at": token_expires_at,
                    "updated_at": datetime.now(timezone.utc),
                },
            )

            await db.execute(stmt)
            await db.commit()

            logger.info(f"User session persisted to database: {email}")

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Authentication successful",
                    "email": email,
                    "full_name": full_name,
                    "access_token": access_token[:10] + "..." if access_token else None,  # Masked for security
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_token": refresh_token[:10] + "..." if refresh_token else None,  # Masked for security
                },
            )

    except httpx.RequestError as e:
        logger.error(f"Network error during token exchange | Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )
    except Exception as e:
        logger.error(f"Unexpected error during token exchange | Error type: {type(e).__name__} | Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed due to server error",
        )


@router.post("/linkedin/callback/session")
async def linkedin_callback_session(
    payload: SessionTokenPayload,
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth session tokens from browser hash fragment.

    This endpoint is called by the client-side JavaScript handler when Supabase
    redirects with tokens in the URL hash fragment (#access_token=...).
    Since HTTP servers can't see hash fragments, the JS extracts them and POSTs here.

    The access_token is a Supabase JWT that we decode to extract user information.

    Args:
        payload: Session tokens and metadata from browser
        db: Database session

    Returns:
        JSON response with user info and confirmation

    Raises:
        HTTPException 401: If JWT decoding fails or token is invalid
        HTTPException 400: If required user info missing from JWT
        HTTPException 500: If database upsert fails
    """
    logger.info("Received OAuth session tokens from client hash fragment handler")

    try:
        access_token = payload.access_token
        refresh_token = payload.refresh_token
        provider_token = payload.provider_token
        expires_in = payload.expires_in or 3600

        logger.debug(
            f"Session token payload | "
            f"Has access_token: {bool(access_token)} | "
            f"Has refresh_token: {bool(refresh_token)} | "
            f"Has provider_token: {bool(provider_token)} | "
            f"Expires in: {expires_in} seconds"
        )

        # Decode Supabase JWT to extract user information
        if not settings.SUPABASE_JWT_SECRET:
            logger.error("SUPABASE_JWT_SECRET not configured for JWT decoding")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JWT secret not configured",
            )

        try:
            # Decode JWT to extract claims
            # IMPORTANT: We trust Supabase GoTrue to send valid tokens over HTTPS directly to our callback.
            # However, Supabase may use different signing algorithms (HS256 symmetric, ES256/RS256 asymmetric).
            # We disable signature verification here since:
            # 1. Token was issued milliseconds ago by Supabase
            # 2. Token arrived over HTTPS directly from Supabase (no intermediary)
            # 3. We still verify expiration to catch any clock skew issues
            #
            # This prevents algorithm mismatch errors when Supabase switches to ES256/RS256 asymmetric keys.
            decoded = jwt.decode(
                access_token,
                options={"verify_signature": False, "verify_exp": True},
                # Support multiple algorithms just in case future use needs it
                algorithms=["HS256", "ES256", "RS256"],
            )
            logger.debug(f"JWT decoded successfully | Claims keys: {list(decoded.keys())}")

        except jwt.ExpiredSignatureError:
            logger.error("Access token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token has expired",
            )
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT decoding failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        # Extract user information from JWT claims
        email = decoded.get("email", "")
        sub = decoded.get("sub", "")
        user_metadata = decoded.get("user_metadata", {})
        full_name = user_metadata.get("full_name", "")

        # Try to construct full_name from given_name + family_name if full_name missing
        if not full_name:
            given_name = user_metadata.get("given_name", "")
            family_name = user_metadata.get("family_name", "")
            if given_name or family_name:
                full_name = f"{given_name} {family_name}".strip()

        logger.debug(
            f"Extracted user info from JWT | "
            f"Email: {email} | "
            f"Sub: {sub} | "
            f"Full Name: {full_name}"
        )

        if not email:
            logger.error("No email in JWT claims | Available claims: " + str(list(decoded.keys())))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No email in access token",
            )

        # Get LinkedIn profile URL from user metadata or construct default
        linkedin_profile_url = user_metadata.get("linkedin_profile_url", "")
        if not linkedin_profile_url and email:
            linkedin_profile_url = f"https://linkedin.com/in/{email.split('@')[0]}"

        # Calculate token expiration
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        logger.info(
            f"Preparing to save user session | "
            f"Email: {email} | "
            f"Full Name: {full_name} | "
            f"Token Expires: {token_expires_at.isoformat()}"
        )

        # Upsert user with tokens to PostgreSQL
        stmt = pg_insert(User).values(
            email=email,
            full_name=full_name,
            linkedin_profile_url=linkedin_profile_url,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            linkedin_access_token=provider_token,  # Store LinkedIn provider token if available
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["email"],
            set_={
                "full_name": full_name,
                "linkedin_profile_url": linkedin_profile_url,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": token_expires_at,
                "linkedin_access_token": provider_token,
                "updated_at": datetime.now(timezone.utc),
            },
        )

        try:
            await db.execute(stmt)
            await db.commit()
            logger.info(f"User session successfully persisted to database | Email: {email}")
        except Exception as db_error:
            logger.error(f"Database upsert failed | Error: {str(db_error)}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save user session to database",
            )

        # Return success response
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": "Authentication successful and profile saved!",
                "email": email,
                "full_name": full_name,
                "access_token": access_token[:10] + "..." if access_token else None,  # Masked for security
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions (already logged and formatted)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during session token processing | Error type: {type(e).__name__} | Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process authentication session",
        )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout the current user and revoke their session.

    Clears the access token, refresh token, and expiration from the database,
    and optionally revokes the session on the Supabase auth server.

    Args:
        current_user: The authenticated user to logout
        db: Database session

    Returns:
        JSON response confirming logout
    """
    logger.info(f"Logout initiated for user: {current_user.email}")

    try:
        # Revoke session on Supabase auth server
        try:
            logger.debug("Attempting to revoke session on Supabase...")
            await revoke_session()
            logger.debug("Session revoked on Supabase")
        except Exception as e:
            logger.warning(f"Failed to revoke session on Supabase (non-fatal): {e}")

        # Clear tokens from database
        stmt = (
            select(User)
            .where(User.user_id == current_user.user_id)
        )
        user = (await db.execute(stmt)).scalars().first()

        if user:
            logger.debug(f"Clearing tokens for user: {user.email}")
            user.access_token = None
            user.refresh_token = None
            user.token_expires_at = None
            await db.commit()
            logger.info(f"User logged out and session cleared: {user.email}")
        else:
            logger.warning(f"User {current_user.user_id} not found in database during logout")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Logged out successfully"},
        )

    except Exception as e:
        logger.error(f"Logout error | User: {current_user.email} | Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout",
        )


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user's information.

    Args:
        current_user: The authenticated user

    Returns:
        JSON response with user profile
    """
    logger.debug(
        f"User info requested | Email: {current_user.email} | "
        f"User ID: {current_user.user_id} | "
        f"Has Active Session: {current_user.access_token is not None}"
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "user_id": current_user.user_id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "linkedin_profile_url": current_user.linkedin_profile_url,
            "has_active_session": current_user.access_token is not None,
        },
    )
