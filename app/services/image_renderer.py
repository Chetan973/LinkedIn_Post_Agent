"""LinkedIn image renderer - supports dual branding modes.

Mode A - Blank Template:
  Renderer draws profile photo, display name, designation, badge dynamically

Mode B - Pre-branded Template:
  Renderer only draws AI-generated thought (template is immutable)

Behavior determined by BrandingConfig.
"""

import logging
import io
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from app.branding.config import BrandingConfig

logger = logging.getLogger(__name__)

# LinkedIn image specifications
LINKEDIN_WIDTH = 1080
LINKEDIN_HEIGHT = 1350


class LinkedInImageRenderer:
    """Renders LinkedIn images with configurable branding support.

    Supports two rendering modes:
    - Mode A: Blank template - renders profile, name, role, badge dynamically
    - Mode B: Pre-branded template - renders only thought (immutable template)

    Behavior determined by BrandingConfig.template_type.
    """

    def __init__(self, branding_config: "BrandingConfig"):
        """Initialize renderer with branding configuration.

        Args:
            branding_config: BrandingConfig with template and rendering instructions

        Raises:
            FileNotFoundError: If template file not found
        """
        self.config = branding_config
        self.template_path = Path(branding_config.template_path)

        logger.info(f"Initializing renderer: {self.config}")

        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        logger.info(f"Template loaded: {self.template_path} (type={branding_config.template_type})")

    def render(
        self,
        thought: str,
        profile_name: Optional[str] = None,
        profile_role: Optional[str] = None,
        font_path: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> bytes:
        """Render LinkedIn image based on branding configuration.

        Rendering behavior determined by BrandingConfig:
        - If template_type="blank": Renders profile elements + thought
        - If template_type="prebranded": Renders thought only

        Args:
            thought: AI-generated thought (8-12 words, one sentence)
            profile_name: Display name (used only if config.draw_name=True)
            profile_role: Designation/headline (used only if config.draw_role=True)
            font_path: Optional path to TTF font
            save_path: Optional path to save PNG locally

        Returns:
            PNG image bytes ready for LinkedIn upload

        Raises:
            Exception: If rendering fails
        """
        try:
            logger.debug(f"Starting render (mode={self.config.template_type}): {thought[:50]}...")

            # Step 1: Load template
            img = Image.open(self.template_path).convert("RGB")
            logger.debug(f"Template loaded: {img.size}")

            # Step 2: Prepare for text rendering
            draw = ImageDraw.Draw(img)

            # Load fonts (with fallback)
            fonts = self._load_fonts(font_path)

            # Step 3: Render based on template type
            if self.config.template_type == "blank":
                # Mode A: Draw all elements
                logger.debug("Mode A: Rendering blank template with profile elements")
                if self.config.draw_profile:
                    logger.debug("Drawing profile photo placeholder")
                if self.config.draw_name and profile_name:
                    self._render_text(draw, profile_name, fonts["name"], "top-left")
                if self.config.draw_role and profile_role:
                    self._render_text(draw, profile_role, fonts["role"], "below-name")
                if self.config.draw_badge:
                    self._render_badge(draw, 50, 50, fonts["role"])
                self._render_thought_centered(draw, thought, fonts["thought"], img.size)
            else:
                # Mode B: Draw thought only (template is immutable)
                logger.debug("Mode B: Rendering pre-branded template (thought only)")
                self._render_thought_centered(draw, thought, fonts["thought"], img.size)

            # Step 4: Save if requested
            if save_path:
                try:
                    img.save(save_path, "PNG", quality=95)
                    logger.info(f"Image saved: {save_path}")
                except Exception as e:
                    logger.error(f"Failed to save image: {str(e)}")
                    raise

            # Step 5: Return PNG bytes
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", quality=95)
            buffer.seek(0)
            image_bytes = buffer.getvalue()

            logger.info(f"Image rendered: {len(image_bytes)} bytes")
            return image_bytes

        except Exception as e:
            logger.error(f"Rendering failed: {str(e)}", exc_info=True)
            raise

    def _load_fonts(self, font_path: Optional[str]) -> dict:
        """Load all required fonts with fallbacks.

        Args:
            font_path: Optional path to TTF font file

        Returns:
            Dictionary with fonts for different purposes
        """
        default_font = ImageFont.load_default()
        fonts = {
            "name": default_font,
            "role": default_font,
            "thought": default_font,
        }

        if font_path:
            font_path_obj = Path(font_path)
            if font_path_obj.exists():
                try:
                    fonts["name"] = ImageFont.truetype(str(font_path_obj), size=36)
                    fonts["role"] = ImageFont.truetype(str(font_path_obj), size=24)
                    fonts["thought"] = ImageFont.truetype(str(font_path_obj), size=32)
                    logger.debug(f"Loaded TTF font: {font_path}")
                except (OSError, IOError) as e:
                    logger.warning(f"Could not load font: {str(e)}. Using default.")
            else:
                logger.warning(f"Font not found: {font_path}. Using default.")

        return fonts

    def _render_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        position: str,
    ) -> None:
        """Render text at specified position.

        Args:
            draw: PIL ImageDraw object
            text: Text to render
            font: Font for rendering
            position: "top-left", "below-name", or "center"
        """
        white = (255, 255, 255)

        if position == "top-left":
            draw.text((50, 50), text, font=font, fill=white)
        elif position == "below-name":
            draw.text((50, 95), text, font=font, fill=white)
        elif position == "center":
            self._render_thought_centered(draw, text, font)

    def _render_badge(
        self,
        draw: ImageDraw.ImageDraw,
        name_x: int,
        name_y: int,
        role_font: ImageFont.FreeTypeFont,
    ) -> None:
        """Draw verification badge next to display name.

        Args:
            draw: PIL ImageDraw object
            name_x: X position of profile name
            name_y: Y position of profile name
            role_font: Font for checkmark (uses smaller font)
        """
        try:
            badge_x = name_x + 300
            badge_y = name_y - 5
            badge_radius = 15
            badge_color = (0, 120, 215)  # LinkedIn blue
            white = (255, 255, 255)

            # Draw blue circle
            draw.ellipse(
                [
                    (badge_x - badge_radius, badge_y - badge_radius),
                    (badge_x + badge_radius, badge_y + badge_radius),
                ],
                fill=badge_color,
                outline=white,
                width=2,
            )

            # Draw white checkmark
            draw.text(
                (badge_x - 6, badge_y - 10), "✓", font=role_font, fill=white
            )

            logger.debug(f"Badge rendered at ({badge_x}, {badge_y})")

        except Exception as e:
            logger.warning(f"Could not draw badge: {str(e)}")

    def _render_thought_centered(
        self,
        draw: ImageDraw.ImageDraw,
        thought: str,
        font: ImageFont.FreeTypeFont,
        img_size: Optional[tuple[int, int]] = None,
    ) -> None:
        """Render thought text horizontally centered, white, up to 3 lines.

        Vertical placement:
        - If BrandingConfig.thought_top_y is set, the first line starts at that
          absolute y. Use this for pre-branded templates where the brand block
          (photo, name, role, badge) sits mid-image and the thought must appear
          BELOW it rather than on top of it.
        - Otherwise the block is vertically centered on the ACTUAL image height.

        Args:
            draw: PIL ImageDraw object
            thought: Thought text
            font: Font for rendering
            img_size: (width, height) of the template. Falls back to the
                LinkedIn portrait defaults when not supplied.
        """
        width, height = img_size if img_size else (LINKEDIN_WIDTH, LINKEDIN_HEIGHT)

        wrapped_lines = self._wrap_text(thought, max_lines=3)

        line_height = 50
        total_height = len(wrapped_lines) * line_height

        anchor = getattr(self.config, "thought_top_y", None)
        if anchor is not None:
            start_y = int(anchor)
            # Keep the block on-canvas if the thought wraps to more lines
            # than the anchor leaves room for.
            max_start = height - total_height - 20
            if start_y > max_start:
                logger.warning(
                    f"thought_top_y={anchor} leaves no room for "
                    f"{len(wrapped_lines)} lines on a {width}x{height} template. "
                    f"Clamping to {max_start}."
                )
                start_y = max(20, max_start)
            placement = f"anchored below brand block at y={start_y}"
        else:
            start_y = (height - total_height) // 2
            placement = f"centered on {width}x{height}"

        text_color = (255, 255, 255)

        for i, line in enumerate(wrapped_lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]

            x = (width - text_width) // 2
            y = start_y + (i * line_height)

            draw.text((x, y), line, font=font, fill=text_color)

        logger.info(
            f"Rendered thought ({len(wrapped_lines)} lines, white text, {placement})"
        )

    @staticmethod
    def _wrap_text(text: str, max_lines: int = 3) -> list[str]:
        """Wrap text to maximum lines.

        Args:
            text: Text to wrap
            max_lines: Maximum lines (default 3)

        Returns:
            List of wrapped lines
        """
        words = text.split()
        lines = []
        current_line = []

        # Rough estimate: ~20 chars per line at 32pt font
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


async def render_linkedin_image(
    branding_config: "BrandingConfig",
    thought: str,
    profile_name: Optional[str] = None,
    profile_role: Optional[str] = None,
    font_path: Optional[str] = None,
    save_path: Optional[str] = None,
) -> bytes:
    """Render LinkedIn image with branding configuration.

    Supports both blank and pre-branded templates via BrandingConfig.

    Args:
        branding_config: BrandingConfig with template and rendering instructions
        thought: AI-generated thought (8-12 words, one sentence)
        profile_name: Display name (used only if config.draw_name=True)
        profile_role: Designation/headline (used only if config.draw_role=True)
        font_path: Optional path to TTF font
        save_path: Optional path to save PNG locally

    Returns:
        PNG image bytes ready for LinkedIn upload

    Raises:
        FileNotFoundError: If template not found
        Exception: If rendering fails
    """
    if not thought:
        raise ValueError("Thought is required for rendering")

    renderer = LinkedInImageRenderer(branding_config)
    image_bytes = renderer.render(
        thought=thought,
        profile_name=profile_name,
        profile_role=profile_role,
        font_path=font_path,
        save_path=save_path,
    )

    logger.info(f"Render complete: {len(image_bytes)} bytes")
    return image_bytes
