"""Brand resolver - URN to BrandingConfig resolution.

Resolves branding configuration for authenticated LinkedIn user.
Supports two rendering modes via BrandingConfig:
- Blank templates: Renderer draws profile elements
- Pre-branded templates: Renderer only draws thought
"""

from app.branding.config import BrandingConfig, branding_registry


class BrandResolver:
    """Resolves branding configuration for authenticated LinkedIn user.

    Single responsibility: Map person_urn → BrandingConfig

    Supports two branding modes:
    - Mode A: Blank template - renderer draws profile, name, role, badge
    - Mode B: Pre-branded template - renderer only draws thought
    """

    @staticmethod
    def get_branding_config(person_urn: str) -> BrandingConfig:
        """Get branding configuration for authenticated user.

        Args:
            person_urn: LinkedIn Person URN (e.g., "urn:li:person:ABC123")

        Returns:
            BrandingConfig with template path and rendering instructions
            Always returns valid config (falls back to default if unmapped)
        """
        if not person_urn:
            # No URN provided, use default
            return branding_registry.get_config("")

        # Look up configuration for this URN
        config = branding_registry.get_config(person_urn)

        return config
