"""Branding configuration models and dataclasses.

Defines the BrandingConfig that encapsulates all branding information
per authenticated LinkedIn user. Never hardcodes user details.
"""

from typing import Optional
from pydantic import BaseModel, Field
from dataclasses import dataclass


class BrandingConfig(BaseModel):
    """Complete branding configuration for an authenticated LinkedIn user.

    Always identified by person_urn (never by username).
    All user-specific data is fetched from LinkedIn, never hardcoded.
    """

    # User Identity (from LinkedIn)
    person_urn: str = Field(
        ...,
        description="LinkedIn Person URN (urn:li:person:XXXXX). Primary identifier."
    )
    display_name: str = Field(
        ...,
        description="User's display name from LinkedIn profile. Fetched via /rest/me."
    )
    headline: str = Field(
        ...,
        description="User's current LinkedIn headline. Fallback to config if unavailable."
    )

    # Image Assets
    template_path: str = Field(
        default="assets/branding/linkedin_template.png",
        description="Local path to branding template image (1080x1350 PNG)."
    )
    profile_image_url: Optional[str] = Field(
        default=None,
        description="User's LinkedIn profile photo URL. Optional, gracefully falls back."
    )

    # Visual Styling
    theme: str = Field(
        default="dark",
        description="Visual theme: 'dark' or 'light'."
    )
    primary_color: str = Field(
        default="#0077B5",
        description="Primary brand color (LinkedIn blue by default)."
    )
    text_color: str = Field(
        default="#FFFFFF",
        description="Text color (white by default for dark theme)."
    )
    secondary_color: str = Field(
        default="#B4B4B4",
        description="Secondary text color (gray by default)."
    )

    # Fonts
    font_path: str = Field(
        default="assets/fonts/Inter_18pt-SemiBold.ttf",
        description="Path to TTF font file for text rendering."
    )

    # Metadata
    created_at: Optional[str] = Field(
        default=None,
        description="When this configuration was created."
    )
    last_updated: Optional[str] = Field(
        default=None,
        description="When this configuration was last updated."
    )

    class Config:
        """Pydantic configuration."""
        validate_assignment = True


class BrandingRegistry:
    """In-memory registry mapping person_urn to BrandingConfig.

    In a production system, this would be loaded from a database.
    For now, supports both code-based and programmatic registration.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._registry: dict[str, BrandingConfig] = {}
        self._default_template = "assets/branding/linkedin_template.png"

    def register(self, config: BrandingConfig) -> None:
        """Register a branding configuration for a user.

        Args:
            config: BrandingConfig with person_urn as key

        Raises:
            ValueError: If person_urn is empty
        """
        if not config.person_urn:
            raise ValueError("person_urn is required for registration")

        self._registry[config.person_urn] = config

    def get(self, person_urn: str) -> BrandingConfig:
        """Get branding configuration for a user.

        Falls back to default if user-specific config not found.

        Args:
            person_urn: LinkedIn Person URN

        Returns:
            BrandingConfig (user-specific or default)
        """
        if person_urn in self._registry:
            return self._registry[person_urn]

        # Return default config (backward compatibility)
        return BrandingConfig(
            person_urn=person_urn,
            display_name="LinkedIn User",
            headline="",
            template_path=self._default_template,
            profile_image_url=None
        )

    def list_all(self) -> list[BrandingConfig]:
        """List all registered configurations.

        Returns:
            List of all BrandingConfig entries
        """
        return list(self._registry.values())

    def unregister(self, person_urn: str) -> bool:
        """Unregister a user's branding configuration.

        Args:
            person_urn: LinkedIn Person URN

        Returns:
            True if found and removed, False if not found
        """
        if person_urn in self._registry:
            del self._registry[person_urn]
            return True
        return False


# Global registry instance (singleton pattern)
branding_registry = BrandingRegistry()


def register_default_branding() -> None:
    """Register default branding configurations.

    This is called at application startup.
    Example: Register specific configs for known users.
    """
    # Example: Register Pranav's branding if URN is known
    # In practice, load this from config file or database
    pass
