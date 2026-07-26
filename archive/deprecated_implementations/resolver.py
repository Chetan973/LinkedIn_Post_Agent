"""Brand resolver service.

Maps authenticated LinkedIn user (by person_urn) to their branding configuration.
Combines LinkedIn profile data with stored branding preferences.
Never hardcodes user information.
"""

import logging
from typing import Optional

from app.branding.config import BrandingConfig, branding_registry
from app.branding.profile_service import LinkedInProfile

logger = logging.getLogger(__name__)


class BrandResolver:
    """Resolves the complete branding configuration for an authenticated user.

    Process:
    1. Take LinkedIn profile (from /rest/me)
    2. Look up user-specific branding preferences (from registry)
    3. Merge/override with user preferences
    4. Return complete BrandingConfig
    """

    @staticmethod
    def resolve(
        profile: LinkedInProfile,
        custom_template_path: Optional[str] = None
    ) -> BrandingConfig:
        """Resolve complete branding configuration for a user.

        Combines LinkedIn profile data with registered branding preferences.
        Falls back gracefully if preferences don't exist.

        Args:
            profile: LinkedInProfile fetched from LinkedIn /rest/me
            custom_template_path: Optional override for template path

        Returns:
            BrandingConfig with all fields populated
        """
        person_urn = profile.person_urn

        logger.info(
            f"Resolving branding for user",
            extra={"person_urn": person_urn, "display_name": profile.display_name}
        )

        # Step 1: Get registered preferences (if any)
        registered_config = branding_registry.get(person_urn)

        # Step 2: Create merged config
        # Start with registered config, override with LinkedIn profile data
        config = BrandingConfig(
            person_urn=person_urn,
            display_name=profile.display_name or registered_config.display_name,
            headline=profile.headline or registered_config.headline or "",
            template_path=custom_template_path or registered_config.template_path,
            profile_image_url=profile.profile_image_url or registered_config.profile_image_url,
            theme=registered_config.theme,
            primary_color=registered_config.primary_color,
            text_color=registered_config.text_color,
            secondary_color=registered_config.secondary_color,
            font_path=registered_config.font_path,
        )

        logger.info(
            f"Branding resolved",
            extra={
                "person_urn": person_urn,
                "template": config.template_path,
                "has_profile_image": bool(config.profile_image_url)
            }
        )

        return config

    @staticmethod
    def resolve_by_urn(
        person_urn: str,
        display_name: Optional[str] = None,
        headline: Optional[str] = None,
        custom_template_path: Optional[str] = None
    ) -> BrandingConfig:
        """Resolve branding for a user identified by person_urn only.

        Useful when you have the URN but haven't fetched profile yet.
        Falls back to registered config or defaults.

        Args:
            person_urn: LinkedIn Person URN
            display_name: Optional override for display name
            headline: Optional override for headline
            custom_template_path: Optional override for template

        Returns:
            BrandingConfig (may use defaults if not registered)
        """
        logger.info(
            f"Resolving branding by URN",
            extra={"person_urn": person_urn}
        )

        # Create pseudo-profile from URN
        profile = LinkedInProfile(
            person_urn=person_urn,
            display_name=display_name,
            headline=headline,
            profile_image_url=None,
            email=None
        )

        return BrandResolver.resolve(profile, custom_template_path)
