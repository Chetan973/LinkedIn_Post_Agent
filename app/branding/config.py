"""Branding configuration - URN to BrandingConfig mapping.

Supports two branding modes:
- Mode A: Blank template (renderer draws profile, name, role, badge)
- Mode B: Pre-branded template (renderer only draws thought)

Configuration driven by BrandingConfig for each user.
"""

import logging
from pathlib import Path
from typing import Optional, Literal

from app.core.config import settings

logger = logging.getLogger(__name__)


class BrandingConfig:
    """Configuration for how a branding template should be rendered.

    Determines whether the renderer should draw profile elements or
    assume they're already in the template.

    Attributes:
        template_path: Path to branding template image file
        template_type: Either "blank" or "prebranded"
        display_name: Name to draw (blank templates only). None = fall back to settings.
        display_role: Designation to draw (blank templates only). None = fall back to settings.
        thought_top_y: Absolute y where the thought's first line starts. Set this
            for pre-branded templates whose brand block sits mid-image, so the
            thought lands BELOW the logo/name instead of over it. None = center.
        draw_profile: Whether to draw profile photo
        draw_name: Whether to draw display name
        draw_role: Whether to draw designation/headline
        draw_badge: Whether to draw verified badge
    """

    def __init__(
        self,
        template_path: str,
        template_type: Literal["blank", "prebranded"] = "blank",
        display_name: Optional[str] = None,
        display_role: Optional[str] = None,
        thought_top_y: Optional[int] = None,
        draw_profile: bool = True,
        draw_name: bool = True,
        draw_role: bool = True,
        draw_badge: bool = True,
    ):
        """Initialize branding configuration.

        Args:
            template_path: Path to branding template image
            template_type: "blank" for renderer to draw elements, "prebranded" for immutable template
            display_name: Name drawn on blank templates. Ignored when prebranded.
            display_role: Designation drawn on blank templates. Ignored when prebranded.
            thought_top_y: Absolute y for the thought's first line. None = center.
            draw_profile: Whether renderer should draw profile photo
            draw_name: Whether renderer should draw display name
            draw_role: Whether renderer should draw designation
            draw_badge: Whether renderer should draw verified badge
        """
        self.template_path = template_path
        self.template_type = template_type
        self.display_name = display_name
        self.display_role = display_role
        self.thought_top_y = thought_top_y
        self.draw_profile = draw_profile
        self.draw_name = draw_name
        self.draw_role = draw_role
        self.draw_badge = draw_badge

    def __repr__(self) -> str:
        return (
            f"BrandingConfig(template_path={self.template_path}, "
            f"template_type={self.template_type}, "
            f"display_name={self.display_name}, "
            f"display_role={self.display_role}, "
            f"thought_top_y={self.thought_top_y}, "
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


# LinkedIn feed image aspect ratios, as (label, width/height).
# The rendered output inherits the template's dimensions verbatim, so a template
# that is not one of these will publish at a non-standard size.
LINKEDIN_STANDARD_RATIOS = (
    ("1:1 square", 1.0),
    ("4:5 portrait", 0.8),
    ("1.91:1 landscape", 1.91),
)
_RATIO_TOLERANCE = 0.02


def _log_template_dimensions(label: str, template_path: str) -> None:
    """Log a template's size and warn if it is not a LinkedIn-standard ratio.

    Cheap startup sanity check - catches a swapped or mis-exported template
    before it produces oddly proportioned posts.
    """
    try:
        from PIL import Image

        with Image.open(template_path) as img:
            width, height = img.size

        ratio = width / height if height else 0
        match = next(
            (name for name, r in LINKEDIN_STANDARD_RATIOS if abs(ratio - r) < _RATIO_TOLERANCE),
            None,
        )

        if match:
            logger.info(
                f"Template for {label}: {width}x{height} ({match}) - standard"
            )
        else:
            logger.warning(
                f"Template for {label}: {width}x{height} (ratio {ratio:.3f}) is NOT a "
                f"LinkedIn standard size. Expected 1:1, 4:5, or 1.91:1. "
                f"Posts will render at this non-standard shape."
            )
    except Exception as e:
        logger.warning(f"Could not read dimensions for {label}'s template: {str(e)}")


def register_branding_templates() -> None:
    """Register per-user branding templates from environment configuration.

    Call this once during application startup (see app/api/main.py lifespan).

    Registered mappings:
      CHETAN_PERSON_URN -> assets/branding/linkedin_template.png
          Blank template. Renderer draws name, role, badge, then the thought.

      PRANAV_PERSON_URN -> assets/branding/Pranav_Linkedin_Template.jpeg
          Pre-branded template. Photo, name, role and badge are already baked
          into the image, so the renderer draws ONLY the generated thought.

    URNs are read from settings so no personal identifiers live in source.
    A blank or missing URN is skipped with a warning rather than failing
    startup - the default blank template still applies to unmapped users.
    """
    registrations = [
        (
            settings.CHETAN_PERSON_URN,
            "Chetan P",
            BrandingConfig(
                template_path="assets/branding/linkedin_template.png",
                template_type="blank",
                display_name="Chetan P",
                display_role="Gen AI Engineer",
                draw_profile=True,
                draw_name=True,
                draw_role=True,
                draw_badge=True,
            ),
        ),
        (
            settings.PRANAV_PERSON_URN,
            "Pranav kumar",
            BrandingConfig(
                template_path="assets/branding/Pranav_Linkedin_Template.jpeg",
                template_type="prebranded",
                display_name="Pranav kumar",
                display_role="DevOps AI Engineer",
                # The brand block (photo + name + role + badge) sits mid-canvas
                # on this 1080x1080 template and ends near y=505. Anchor the
                # thought just below it so it never overlaps the logo/name.
                thought_top_y=settings.PRANAV_THOUGHT_TOP_Y,
                draw_profile=False,
                draw_name=False,
                draw_role=False,
                draw_badge=False,
            ),
        ),
    ]

    for person_urn, label, config in registrations:
        if not person_urn:
            logger.warning(
                f"No URN configured for {label}. Skipping registration - "
                f"this user will fall back to the default blank template."
            )
            continue

        if not Path(config.template_path).exists():
            logger.warning(
                f"Template for {label} not found at '{config.template_path}'. "
                f"Registering anyway; rendering will fail until the file exists."
            )
        else:
            _log_template_dimensions(label, config.template_path)

        try:
            branding_registry.register(person_urn, config)
            logger.info(
                f"Registered branding for {label} | "
                f"urn={person_urn} | template={config.template_path} "
                f"({config.template_type})"
            )
        except ValueError as e:
            logger.error(f"Failed to register branding for {label}: {str(e)}")
