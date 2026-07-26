"""Branding module - URN-based branding configuration and resolution.

This module handles branding-related functionality:
- BrandingConfig: Configuration for how a template should be rendered
- BrandingRegistry: Maps LinkedIn Person URN to BrandingConfig
- BrandResolver: Resolves BrandingConfig for authenticated user

Supports two branding modes:
- Blank templates: Renderer draws profile, name, role, badge dynamically
- Pre-branded templates: Renderer only draws thought (template is immutable)

Never hardcodes user information. Always uses person_urn as unique identifier.
"""

from app.branding.config import BrandingConfig, BrandingRegistry, branding_registry, register_branding_templates
from app.branding.resolver import BrandResolver

__all__ = [
    "BrandingConfig",
    "BrandingRegistry",
    "branding_registry",
    "register_branding_templates",
    "BrandResolver",
]
