"""Branding configuration - URN to BrandingConfig mapping.

Supports two branding modes:
- Mode A: Blank template (renderer draws profile, name, role, badge)
- Mode B: Pre-branded template (renderer only draws thought)

Configuration driven by BrandingConfig for each user.
"""

from typing import Optional, Literal


class BrandingConfig:
    """Configuration for how a branding template should be rendered.

    Determines whether the renderer should draw profile elements or
    assume they're already in the template.

    Attributes:
        template_path: Path to branding template image file
        template_type: Either "blank" or "prebranded"
        draw_profile: Whether to draw profile photo
        draw_name: Whether to draw display name
        draw_role: Whether to draw designation/headline
        draw_badge: Whether to draw verified badge
    """

    def __init__(
        self,
        template_path: str,
        template_type: Literal["blank", "prebranded"] = "blank",
        draw_profile: bool = True,
        draw_name: bool = True,
        draw_role: bool = True,
        draw_badge: bool = True,
    ):
        """Initialize branding configuration.

        Args:
            template_path: Path to branding template image
            template_type: "blank" for renderer to draw elements, "prebranded" for immutable template
            draw_profile: Whether renderer should draw profile photo
            draw_name: Whether renderer should draw display name
            draw_role: Whether renderer should draw designation
            draw_badge: Whether renderer should draw verified badge
        """
        self.template_path = template_path
        self.template_type = template_type
        self.draw_profile = draw_profile
        self.draw_name = draw_name
        self.draw_role = draw_role
        self.draw_badge = draw_badge

    def __repr__(self) -> str:
        return (
            f"BrandingConfig(template_path={self.template_path}, "
            f"template_type={self.template_type}, "
            f"draw_profile={self.draw_profile}, "
            f"draw_name={self.draw_name}, "
            f"draw_role={self.draw_role}, "
            f"draw_badge={self.draw_badge})"
        )


class BrandingRegistry:
    """Maps LinkedIn Person URN to BrandingConfig.

    Stores configurations for different users, supporting both
    blank templates (with dynamic drawing) and pre-branded templates.
    """

    def __init__(self):
        """Initialize registry with default configurations."""
        self._configs: dict[str, BrandingConfig] = {}
        # Default: blank template that requires drawing
        self._default_config = BrandingConfig(
            template_path="assets/branding/linkedin_template.png",
            template_type="blank",
            draw_profile=True,
            draw_name=True,
            draw_role=True,
            draw_badge=True,
        )

    def register(self, person_urn: str, config: BrandingConfig) -> None:
        """Register a person_urn → BrandingConfig mapping.

        Args:
            person_urn: LinkedIn Person URN (e.g., "urn:li:person:ABC123")
            config: BrandingConfig for this user

        Raises:
            ValueError: If person_urn is invalid
        """
        if not person_urn or not person_urn.startswith("urn:li:person:"):
            raise ValueError(f"Invalid person_urn: {person_urn}")

        if not isinstance(config, BrandingConfig):
            raise ValueError("config must be a BrandingConfig instance")

        self._configs[person_urn] = config

    def get_config(self, person_urn: str) -> BrandingConfig:
        """Get branding configuration for a person_urn.

        Falls back to default if URN not registered.

        Args:
            person_urn: LinkedIn Person URN

        Returns:
            BrandingConfig for this user
        """
        return self._configs.get(person_urn, self._default_config)

    def set_default(self, config: BrandingConfig) -> None:
        """Set default branding configuration.

        Args:
            config: BrandingConfig to use as default
        """
        self._default_config = config

    def list_configs(self) -> dict[str, BrandingConfig]:
        """List all registered URN → BrandingConfig mappings.

        Returns:
            Dictionary of all configurations
        """
        return dict(self._configs)


# Global singleton instance
branding_registry = BrandingRegistry()


def register_branding_templates() -> None:
    """Register known branding templates.

    Call this during application startup.
    Example:
        register_branding_templates()

    This function can be extended to load configurations from:
    - Environment variables
    - Configuration file (YAML/JSON)
    - Database
    """
    # Example: Register Pranav's pre-branded template
    # In production, load these from config or environment

    # branding_registry.register(
    #     "urn:li:person:PRANAV_URN_HERE",
    #     BrandingConfig(
    #         template_path="assets/branding/Pranav_Linkedin_Template.jpeg",
    #         template_type="prebranded",
    #         draw_profile=False,
    #         draw_name=False,
    #         draw_role=False,
    #         draw_badge=False,
    #     )
    # )

    pass
