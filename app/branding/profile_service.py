"""LinkedIn profile service to fetch authenticated user details.

Reuses existing OAuth access token to fetch:
- Person URN
- Display Name
- Headline
- Profile Photo URL

Never hardcodes user information.
"""

import logging
import httpx
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LinkedInProfile:
    """Authenticated LinkedIn user's profile information.

    Fetched via /rest/me endpoint. Fields are optional because
    permissions may restrict data access.
    """
    person_urn: str
    display_name: Optional[str] = None
    headline: Optional[str] = None
    profile_image_url: Optional[str] = None
    email: Optional[str] = None


class LinkedInProfileService:
    """Service to fetch authenticated user profile from LinkedIn.

    Uses the existing OAuth access token to call LinkedIn /rest/me endpoint.
    Handles permission limitations gracefully.
    """

    def __init__(self, access_token: str):
        """Initialize service with OAuth access token.

        Args:
            access_token: LinkedIn OAuth access token (from authenticated user)
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202606"
        }

    async def fetch_authenticated_profile(self) -> LinkedInProfile:
        """Fetch the authenticated user's LinkedIn profile.

        Calls GET /rest/me to retrieve:
        - id (person URN)
        - localizedFirstName + localizedLastName (display name)
        - localizedHeadline (current job title)
        - profilePicture (profile photo)

        Returns:
            LinkedInProfile with fetched data

        Raises:
            Exception: If /rest/me call fails or token is invalid
        """
        url = "https://api.linkedin.com/rest/me"

        logger.info("Fetching authenticated LinkedIn user profile")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)

                if response.status_code != 200:
                    logger.error(
                        f"Failed to fetch profile: {response.status_code}",
                        extra={"response": response.text[:500]}
                    )
                    raise Exception(
                        f"LinkedIn /rest/me failed: {response.status_code} - {response.text}"
                    )

                data = response.json()
                logger.info(
                    "Successfully fetched authenticated profile",
                    extra={"person_urn": data.get("id")}
                )

                return self._parse_profile(data)

            except httpx.TimeoutException as e:
                logger.error("Timeout fetching LinkedIn profile", exc_info=True)
                raise Exception(f"LinkedIn API timeout: {str(e)}") from e
            except Exception as e:
                logger.error("Exception fetching LinkedIn profile", exc_info=True)
                raise

    def _parse_profile(self, data: dict) -> LinkedInProfile:
        """Parse LinkedIn /rest/me response into LinkedInProfile.

        Handles optional fields gracefully.

        Args:
            data: JSON response from /rest/me

        Returns:
            LinkedInProfile with parsed data
        """
        person_urn = data.get("id")
        if not person_urn:
            raise ValueError("LinkedIn API response missing 'id' (person URN)")

        # Parse display name (combine first + last name if available)
        first_name = data.get("localizedFirstName", "")
        last_name = data.get("localizedLastName", "")
        display_name = f"{first_name} {last_name}".strip() or "LinkedIn User"

        # Parse headline (current job title)
        headline = data.get("localizedHeadline", "")

        # Parse profile photo (if available and accessible)
        profile_image_url = self._extract_profile_image_url(data)

        # Parse email (often requires r_emailaddress permission)
        email = data.get("emailAddress")

        logger.info(
            f"Parsed profile: {display_name} ({person_urn})",
            extra={
                "headline": headline,
                "has_profile_image": bool(profile_image_url)
            }
        )

        return LinkedInProfile(
            person_urn=person_urn,
            display_name=display_name,
            headline=headline,
            profile_image_url=profile_image_url,
            email=email
        )

    def _extract_profile_image_url(self, data: dict) -> Optional[str]:
        """Extract profile image URL from LinkedIn response.

        LinkedIn profile picture data structure is complex:
        profilePicture: {
            displayImage: "urn:li:digitalmediarecipe:C4D03AQGGnvsB-q15A"
        }

        We'd need the digitalmediarecipe to be converted to actual image URL,
        which requires additional API calls or special handling.

        For now, return None to gracefully fall back to template image.
        Future enhancement: Implement profile image download via
        GET /rest/images/{urn} endpoint.

        Args:
            data: JSON response from /rest/me

        Returns:
            Profile image URL or None if not available/accessible
        """
        try:
            profile_picture = data.get("profilePicture", {})

            # LinkedIn returns URN, not direct URL
            # Would need additional processing
            if profile_picture:
                logger.debug(
                    "Profile picture found but requires additional processing",
                    extra={"picture": str(profile_picture)[:100]}
                )
                # TODO: Implement profile image download if needed

            return None  # Graceful fallback

        except Exception as e:
            logger.warning(f"Error extracting profile image: {str(e)}")
            return None  # Graceful fallback


async def get_authenticated_profile(access_token: str) -> LinkedInProfile:
    """Convenience function to fetch authenticated user profile.

    Args:
        access_token: LinkedIn OAuth access token

    Returns:
        LinkedInProfile with user details
    """
    service = LinkedInProfileService(access_token)
    return await service.fetch_authenticated_profile()
