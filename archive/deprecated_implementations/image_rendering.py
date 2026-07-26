"""Image rendering node for LangGraph workflow.

Renders LinkedIn-compliant images using PIL with template overlay.
Converts AI-generated thought to image bytes for LinkedIn upload.

No external image generation services - uses local PIL/Pillow.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from app.Services.image_renderer import render_linkedin_image
from app.core.config import settings
from app.core.instrumentation import create_context_logger, get_correlation_id

logger = logging.getLogger(__name__)
tracer = create_context_logger(__name__)


async def image_rendering_node(state: dict) -> dict:
    """LangGraph node for rendering LinkedIn image.

    Takes the AI-generated thought and renders it onto a template image.
    Saves image to disk and returns file path for LinkedIn upload.

    The image includes:
    - Profile header (name, role, verification badge) - top-left
    - AI thought (20-35 words) - centered
    - Premium black background template

    Args:
        state: LangGraph state containing:
            - ai_thought: AI-generated thought (20-35 words, plain text)
            - draft_content: Original post content (for context, optional)

    Returns:
        Updated state dict with:
            - image_url: Local file path to saved PNG image
            - image_bytes: PNG bytes ready for LinkedIn upload
            - image_rendered_at: Timestamp of rendering
    """
    cid = get_correlation_id()
    thought = state.get("ai_thought")
    post_id = state.get("post_id", "unknown")

    tracer.info(
        f"[{cid}] ENTER image_rendering_node",
        extra={
            "post_id": post_id,
            "has_thought": bool(thought),
            "thought_preview": thought[:30] if thought else None
        }
    )

    if not thought:
        tracer.warning(f"[{cid}] No thought to render. Returning None image_url.")
        return {
            "image_bytes": None,
            "image_url": None,
            "image_rendered_at": None,
        }

    try:
        tracer.info(f"[{cid}] Calling render_linkedin_image()...")

        # Render image using PIL
        image_bytes = await render_linkedin_image(
            thought=thought,
            profile_name=settings.PROFILE_NAME,
            profile_role=settings.PROFILE_ROLE,
            template_path=settings.TEMPLATE_IMAGE_PATH,
        )

        tracer.info(
            f"[{cid}] render_linkedin_image() returned",
            extra={
                "image_bytes_is_none": image_bytes is None,
                "image_bytes_length": len(image_bytes) if image_bytes else 0
            }
        )

        if not image_bytes:
            tracer.error(f"[{cid}] Image rendering returned empty bytes")
            return {
                "image_bytes": None,
                "image_url": None,
                "image_rendered_at": False,
            }

        tracer.info(
            f"[{cid}] Image rendered successfully",
            extra={"image_bytes": len(image_bytes)}
        )

        # Create output directory for generated images
        output_dir = Path("assets/generated_images")
        os.makedirs(output_dir, exist_ok=True)
        tracer.info(
            f"[{cid}] Output directory ensured",
            extra={"output_dir": str(output_dir.absolute())}
        )

        # Save image to disk with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = output_dir / f"post_{post_id}_{timestamp}.png"

        tracer.info(
            f"[{cid}] Saving image to disk",
            extra={"image_path": str(image_path.absolute())}
        )

        try:
            with open(image_path, "wb") as f:
                f.write(image_bytes)

            tracer.info(
                f"[{cid}] Image saved to disk successfully",
                extra={
                    "image_path": str(image_path.absolute()),
                    "file_exists": image_path.exists(),
                    "file_size": image_path.stat().st_size if image_path.exists() else 0
                }
            )
        except Exception as write_err:
            tracer.error(
                f"[{cid}] Failed to save image to disk",
                exc_info=True
            )
            raise

        return_value = {
            "image_bytes": image_bytes,
            "image_url": str(image_path),
            "image_size_bytes": len(image_bytes),
            "image_rendered_at": True,
        }

        tracer.info(
            f"[{cid}] EXIT image_rendering_node - image_url set",
            extra={
                "image_url": str(image_path),
                "image_url_type": type(str(image_path)).__name__
            }
        )

        return return_value

    except Exception as e:
        tracer.error(
            f"[{cid}] Exception in image_rendering_node",
            exc_info=True
        )
        # Don't fail workflow - image is optional
        tracer.info(f"[{cid}] Returning None for image_url (proceeding without image)")
        return {
            "image_bytes": None,
            "image_url": None,
            "image_rendered_at": False,
        }
