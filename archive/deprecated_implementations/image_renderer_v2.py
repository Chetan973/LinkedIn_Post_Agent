"""Updated image renderer that uses BrandingConfig.

Renders LinkedIn images with user-specific branding.
Receives BrandingConfig instead of individual hardcoded values.
Handles profile images gracefully (with fallback).
"""

import logging
import io
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from app.branding.config import BrandingConfig

logger = logging.getLogger(__name__)

# LinkedIn image specifications
LINKEDIN_WIDTH = 1080
LINKEDIN_HEIGHT = 1350


class LinkedInImageRendererV2:
    """Renders LinkedIn images using BrandingConfig (user-aware).

    Key differences from v1:
    - Receives BrandingConfig instead of individual parameters
    - Uses authenticated user's name and headline (not hardcoded)
    - Supports per-user branding templates
    - Handles profile images with graceful fallback
    """

    def __init__(self, branding_config: BrandingConfig):
        """Initialize renderer with branding configuration.

        Args:
            branding_config: BrandingConfig for authenticated user

        Raises:
            FileNotFoundError: If template or font not found
        """
        self.branding_config = branding_config
        self.template_path = Path(branding_config.template_path)
        self.font_path = Path(branding_config.font_path)

        logger.info(
            f"Initializing ImageRendererV2 for {branding_config.display_name}",
            extra={
                "person_urn": branding_config.person_urn,
                "template": str(self.template_path)
            }
        )

        # Validate template exists
        if not self.template_path.exists():
            logger.warning(
                f"Template not found: {self.template_path}. "
                f"Will create solid background image."
            )
            self.template_path = None
        else:
            logger.info(f"Template loaded: {self.template_path}")

        # Validate font exists
        if not self.font_path.exists():
            logger.warning(f"Font not found: {self.font_path}. Will use default font.")
            self.font_path = None

    def render(
        self,
        thought: str,
        save_path: Optional[str] = None
    ) -> bytes:
        """Render image with thought overlay using branding config.

        Args:
            thought: AI-generated thought (20-35 words, max 3 lines)
            save_path: Optional path to save PNG locally

        Returns:
            PNG image bytes ready for LinkedIn upload

        Raises:
            Exception: If image rendering fails
        """
        try:
            logger.debug(
                f"Starting image render",
                extra={
                    "person": self.branding_config.display_name,
                    "thought_length": len(thought),
                    "thought_preview": thought[:50]
                }
            )

            # Load template or create fallback
            if self.template_path and self.template_path.exists():
                logger.debug(f"Loading template from: {self.template_path}")
                img = Image.open(self.template_path).convert("RGB")
            else:
                logger.debug("Creating solid black background image")
                # Solid black background (premium aesthetic)
                bg_color = (20, 20, 20)  # Very dark gray/black
                img = Image.new("RGB", (LINKEDIN_WIDTH, LINKEDIN_HEIGHT), color=bg_color)

            draw = ImageDraw.Draw(img)

            # Load fonts (with fallback to default)
            name_font = ImageFont.load_default()
            role_font = ImageFont.load_default()
            thought_font = ImageFont.load_default()

            if self.font_path and self.font_path.exists():
                try:
                    name_font = ImageFont.truetype(str(self.font_path), size=36)
                    role_font = ImageFont.truetype(str(self.font_path), size=24)
                    thought_font = ImageFont.truetype(str(self.font_path), size=32)
                    logger.debug(f"Loaded TTF font: {self.font_path}")
                except (OSError, IOError) as e:
                    logger.warning(
                        f"Could not load TTF font ({str(e)}). Using default PIL font."
                    )

            # Draw profile header (top-left)
            try:
                logger.debug("Drawing profile header")
                self._draw_header(
                    draw,
                    self.branding_config.display_name,
                    self.branding_config.headline,
                    name_font,
                    role_font,
                    self.branding_config.text_color,
                    self.branding_config.secondary_color
                )
            except Exception as header_err:
                logger.error(f"Failed to draw profile header: {str(header_err)}", exc_info=True)
                raise

            # Draw thought (centered, max 3 lines)
            try:
                logger.debug("Drawing thought text")
                self._draw_thought(
                    draw,
                    thought,
                    thought_font,
                    self.branding_config.text_color
                )
            except Exception as thought_err:
                logger.error(f"Failed to draw thought: {str(thought_err)}", exc_info=True)
                raise

            # Save if requested
            if save_path:
                try:
                    img.save(save_path, "PNG", quality=95)
                    logger.info(f"Image saved to {save_path}")
                except Exception as save_err:
                    logger.error(f"Failed to save image: {str(save_err)}", exc_info=True)
                    raise

            # Return bytes
            try:
                logger.debug("Encoding image to PNG bytes")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG", quality=95)
                buffer.seek(0)
                image_bytes = buffer.getvalue()
                logger.debug(f"Image encoded successfully: {len(image_bytes)} bytes")
                return image_bytes
            except Exception as encode_err:
                logger.error(f"Failed to encode image: {str(encode_err)}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"Image rendering failed: {str(e)}", exc_info=True)
            raise

    def _draw_header(
        self,
        draw: ImageDraw.ImageDraw,
        name: str,
        role: str,
        name_font: ImageFont.FreeTypeFont,
        role_font: ImageFont.FreeTypeFont,
        text_color: str,
        secondary_color: str
    ) -> None:
        """Draw profile header in top-left corner.

        Args:
            draw: PIL ImageDraw object
            name: User's display name (from LinkedIn)
            role: User's headline (from LinkedIn)
            name_font: Font for name
            role_font: Font for role
            text_color: Hex color for name
            secondary_color: Hex color for role
        """
        x, y = 50, 50

        # Convert hex to RGB tuple
        name_rgb = self._hex_to_rgb(text_color)
        role_rgb = self._hex_to_rgb(secondary_color)

        # Draw name
        draw.text((x, y), name, font=name_font, fill=name_rgb)

        # Draw role below name
        draw.text((x, y + 45), role, font=role_font, fill=role_rgb)

        # Draw verification badge
        try:
            badge_x, badge_y = x + 300, y - 5
            badge_radius = 15
            badge_rgb = self._hex_to_rgb("#0078D7")  # LinkedIn blue

            draw.ellipse(
                [
                    (badge_x - badge_radius, badge_y - badge_radius),
                    (badge_x + badge_radius, badge_y + badge_radius),
                ],
                fill=badge_rgb,
                outline=(255, 255, 255),
                width=2,
            )
            draw.text((badge_x - 6, badge_y - 10), "✓", font=role_font, fill=(255, 255, 255))
        except Exception as e:
            logger.debug(f"Could not draw badge: {str(e)}")

        logger.debug(f"Header drawn: {name} - {role}")

    def _draw_thought(
        self,
        draw: ImageDraw.ImageDraw,
        thought: str,
        font: ImageFont.FreeTypeFont,
        text_color: str
    ) -> None:
        """Draw thought text centered on image.

        Supports up to 3 lines, center-aligned.

        Args:
            draw: PIL ImageDraw object
            thought: Thought text (max 3 lines, 20-35 words)
            font: Font for thought
            text_color: Hex color for text
        """
        # Wrap text to fit within image (max 3 lines)
        wrapped_lines = self._wrap_text_multiline(thought, max_lines=3, max_width=900)

        # Calculate vertical position (center of image)
        line_height = 50
        total_height = len(wrapped_lines) * line_height
        start_y = (LINKEDIN_HEIGHT - total_height) // 2

        # Convert hex to RGB
        text_rgb = self._hex_to_rgb(text_color)

        # Draw each line centered
        for i, line in enumerate(wrapped_lines):
            # Get text width to center it
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (LINKEDIN_WIDTH - text_width) // 2

            y = start_y + (i * line_height)
            draw.text((x, y), line, font=font, fill=text_rgb)

        logger.info(
            f"Drew {len(wrapped_lines)} lines of thought",
            extra={
                "lines": len(wrapped_lines),
                "total_characters": sum(len(line) for line in wrapped_lines)
            }
        )

    def _wrap_text_multiline(
        self,
        text: str,
        max_lines: int = 3,
        max_width: int = 900
    ) -> list[str]:
        """Wrap text to fit within max lines (for 3-line display).

        Args:
            text: Text to wrap
            max_lines: Maximum number of lines (default 3)
            max_width: Maximum width in pixels (approximate)

        Returns:
            List of wrapped lines (up to max_lines)
        """
        words = text.split()
        lines = []
        current_line = []

        # Rough estimate: ~20 chars per line at this font size
        max_chars = 35

        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > max_chars:
                if len(current_line) > 1:
                    current_line.pop()
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []

                if len(lines) >= max_lines:
                    break

        if current_line and len(lines) < max_lines:
            lines.append(" ".join(current_line))

        return lines if lines else [text[:35]]

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple.

        Args:
            hex_color: Hex color (e.g., "#FFFFFF")

        Returns:
            RGB tuple (r, g, b)
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (255, 255, 255)  # Default to white if invalid


async def render_linkedin_image_v2(
    branding_config: BrandingConfig,
    thought: str,
    save_path: Optional[str] = None
) -> bytes:
    """Async wrapper for image rendering with branding config.

    Args:
        branding_config: BrandingConfig for authenticated user
        thought: AI thought (max 3 lines, 20-35 words)
        save_path: Optional path to save PNG locally

    Returns:
        PNG image bytes ready for LinkedIn upload

    Raises:
        ValueError: If thought is None or empty
        Exception: If rendering fails
    """
    if not thought:
        raise ValueError("Thought is required for image rendering")

    renderer = LinkedInImageRendererV2(branding_config)
    image_bytes = renderer.render(thought, save_path)

    logger.info(f"Rendered image using BrandingConfig: {len(image_bytes)} bytes")
    return image_bytes
