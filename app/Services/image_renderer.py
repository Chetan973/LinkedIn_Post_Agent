"""PIL/Pillow-based LinkedIn image rendering with template overlay.

Renders LinkedIn images by overlaying text (profile header + thought) on a
fixed template image. No external image generation services.

Template specs:
- 1080×1350 pixels (portrait)
- Black background (premium aesthetic)
- Profile header with name, role, verification badge (top-left)
- AI-generated thought (20-35 words, centered)
"""

import logging
import io
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise ImportError(
        "Pillow is required for image rendering. "
        "Install with: pip install Pillow"
    )

from app.core.config import settings

logger = logging.getLogger(__name__)

# LinkedIn image specs
LINKEDIN_WIDTH = 1080
LINKEDIN_HEIGHT = 1350


class LinkedInImageRenderer:
    """Renders LinkedIn images by overlaying text on a template."""

    def __init__(
        self,
        template_path: Optional[str] = None,
        font_path: Optional[str] = None,
    ):
        """Initialize renderer with template and font.

        Args:
            template_path: Path to base template (1080×1350). Defaults to config.
            font_path: Path to TTF font file. Defaults to config.

        Raises:
            FileNotFoundError if template or font not found
        """
        self.template_path = Path(template_path or settings.TEMPLATE_IMAGE_PATH)
        self.font_path = Path(font_path or settings.FONTS_PATH) / "Inter_18pt-SemiBold.ttf"

        if not self.template_path.exists():
            logger.warning(
                f"Template not found: {self.template_path}. "
                f"Will create solid black image instead."
            )
            self.template_path = None
        else:
            logger.info(f"Using template: {self.template_path}")

        if not self.font_path.exists():
            logger.warning(f"Font not found: {self.font_path}. Will use default font.")
            self.font_path = None

    def render(
        self,
        thought: str,
        profile_name: Optional[str] = None,
        profile_role: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> bytes:
        """Render image with thought overlay.

        Args:
            thought: AI-generated thought (20-35 words, plain text)
            profile_name: Name for header (defaults to config)
            profile_role: Role/title for header (defaults to config)
            save_path: Optional path to save PNG locally

        Returns:
            PNG image bytes ready for LinkedIn upload

        Raises:
            Exception: If image rendering or encoding fails
        """
        try:
            profile_name = profile_name or settings.PROFILE_NAME
            profile_role = profile_role or settings.PROFILE_ROLE

            logger.debug(f"Starting image render with thought: {thought[:50]}...")

            # Load or create template
            if self.template_path and self.template_path.exists():
                logger.debug(f"Loading template from: {self.template_path}")
                img = Image.open(self.template_path).convert("RGB")
            else:
                # Fallback: solid black background
                logger.warning("Template not found, creating solid black background image")
                img = Image.new("RGB", (LINKEDIN_WIDTH, LINKEDIN_HEIGHT), color=(0, 0, 0))

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
                    logger.warning(f"Could not load TTF font ({str(e)}). Using default PIL font.")

            # 1. Draw profile header (top-left)
            try:
                logger.debug("Drawing profile header...")
                self._draw_header(draw, profile_name, profile_role, name_font, role_font)
            except Exception as header_err:
                logger.error(f"Failed to draw profile header: {str(header_err)}", exc_info=True)
                raise

            # 2. Draw thought (centered, with wrapping)
            try:
                logger.debug("Drawing thought text...")
                self._draw_thought(draw, thought, thought_font)
            except Exception as thought_err:
                logger.error(f"Failed to draw thought: {str(thought_err)}", exc_info=True)
                raise

            # Save if requested
            if save_path:
                try:
                    img.save(save_path, "PNG", quality=95)
                    logger.info(f"Image saved to {save_path}")
                except Exception as save_err:
                    logger.error(f"Failed to save image to {save_path}: {str(save_err)}", exc_info=True)
                    raise

            # Return bytes
            try:
                logger.debug("Encoding image to PNG bytes...")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG", quality=95)
                buffer.seek(0)
                image_bytes = buffer.getvalue()
                logger.debug(f"Image encoded successfully: {len(image_bytes)} bytes")
                return image_bytes
            except Exception as encode_err:
                logger.error(f"Failed to encode image to bytes: {str(encode_err)}", exc_info=True)
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
    ) -> None:
        """Draw profile header in top-left corner.

        Args:
            draw: PIL ImageDraw object
            name: Profile name
            role: Profile role/designation
            name_font: Font for name (larger)
            role_font: Font for role (smaller)
        """
        x, y = 50, 50
        text_color = (255, 255, 255)  # White
        secondary_color = (180, 180, 180)  # Gray

        # Draw name
        draw.text((x, y), name, font=name_font, fill=text_color)

        # Draw role below name
        draw.text((x, y + 45), role, font=role_font, fill=secondary_color)

        # Optional: Draw verification badge (small circle with checkmark)
        try:
            badge_x, badge_y = x + 300, y - 5
            badge_radius = 15
            badge_color = (0, 120, 215)  # LinkedIn blue
            draw.ellipse(
                [
                    (badge_x - badge_radius, badge_y - badge_radius),
                    (badge_x + badge_radius, badge_y + badge_radius),
                ],
                fill=badge_color,
                outline=(255, 255, 255),
                width=2,
            )
            # Draw checkmark
            draw.text(
                (badge_x - 6, badge_y - 10), "✓", font=role_font, fill=(255, 255, 255)
            )
        except Exception as e:
            logger.debug(f"Could not draw badge: {str(e)}")

    def _draw_thought(
        self,
        draw: ImageDraw.ImageDraw,
        thought: str,
        font: ImageFont.FreeTypeFont,
    ) -> None:
        """Draw thought text centered on image.

        Args:
            draw: PIL ImageDraw object
            thought: Thought text (20-35 words)
            font: Font for thought
        """
        # Wrap text to fit within image width
        wrapped_lines = self._wrap_text(thought, max_width=900)

        # Calculate vertical position (center of image)
        total_height = len(wrapped_lines) * 50  # Approximate line height
        start_y = (LINKEDIN_HEIGHT - total_height) // 2

        # Draw each line centered
        text_color = (255, 255, 255)  # White
        for i, line in enumerate(wrapped_lines):
            # Get text width to center it
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (LINKEDIN_WIDTH - text_width) // 2

            y = start_y + (i * 50)
            draw.text((x, y), line, font=font, fill=text_color)

        logger.info(f"Drew {len(wrapped_lines)} lines of thought")

    def _wrap_text(self, text: str, max_width: int = 900) -> list[str]:
        """Wrap text to fit within max width.

        Uses simple word-based wrapping (doesn't account for font width variations).

        Args:
            text: Text to wrap
            max_width: Maximum width in pixels (approximate)

        Returns:
            List of wrapped lines
        """
        words = text.split()
        lines = []
        current_line = []

        # Very rough estimate: ~20 chars per line at this font size
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

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [text[:max_chars]]


async def render_linkedin_image(
    thought: str,
    profile_name: Optional[str] = None,
    profile_role: Optional[str] = None,
    save_path: Optional[str] = None,
    template_path: Optional[str] = None,
) -> bytes:
    """Async wrapper for image rendering.

    Args:
        thought: AI thought (20-35 words, plain text, no markdown)
        profile_name: Override default profile name from config
        profile_role: Override default profile role from config
        save_path: Optional path to save PNG locally
        template_path: Override default template path

    Returns:
        PNG image bytes ready for LinkedIn upload

    Raises:
        ValueError if thought is None or empty
    """
    if not thought:
        raise ValueError("Thought is required for image rendering")

    renderer = LinkedInImageRenderer(template_path=template_path)
    image_bytes = renderer.render(
        thought, profile_name, profile_role, save_path
    )

    logger.info(f"Rendered image: {len(image_bytes)} bytes")
    return image_bytes
