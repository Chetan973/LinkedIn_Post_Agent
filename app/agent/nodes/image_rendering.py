"""Minimal image rendering node - render thought onto immutable template.

Workflow:
1. Get authenticated person_urn (from state)
2. Resolve template path (via BrandResolver)
3. Render thought onto template (via MinimalImageRenderer)
4. Save to disk
5. Return image_url

Template is immutable source of truth.
Only the thought is rendered dynamically.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from app.Services.image_renderer import render_linkedin_image
from app.branding.resolver import BrandResolver
from app.core.config import settings
from app.core.instrumentation import create_context_logger, get_correlation_id

logger = logging.getLogger(__name__)
tracer = create_context_logger(__name__)


async def image_rendering_node(state: dict) -> dict:
    """Render thought onto immutable branding template.

    Workflow:
    1. Extract person_urn from state
    2. Resolve template path (BrandResolver)
    3. Render thought onto template
    4. Save to disk
    5. Return image_url

    Args:
        state: LangGraph state containing:
            - ai_thought: Generated thought (8-12 words, one sentence)
            - person_urn: LinkedIn Person URN (authenticated user)
            - post_id: For file naming

    Returns:
        Updated state dict with:
            - image_bytes: PNG bytes (in-memory)
            - image_url: Local file path to saved PNG
            - image_size_bytes: File size in bytes
            - image_rendered_at: True if successful

    Note:
        If person_urn not available, gracefully skips image rendering.
        Text-only posts still work (image is optional).
    """
    cid = get_correlation_id()
    thought = state.get("ai_thought")
    person_urn = state.get("person_urn")
    post_id = state.get("post_id", "unknown")

    tracer.info(
        f"[{cid}] ENTER image_rendering_node",
        extra={
            "post_id": post_id,
            "has_thought": bool(thought),
            "has_person_urn": bool(person_urn),
            "thought_preview": thought[:30] if thought else None
        }
    )

    # Validation
    if not thought:
        tracer.warning(f"[{cid}] No thought to render. Skipping image.")
        return {
            "image_bytes": None,
            "image_url": None,
            "image_rendered_at": False,
        }

    try:
        # STEP 1: Resolve branding configuration
        tracer.info(f"[{cid}] STEP 1: Resolving branding configuration...")

        if not person_urn:
            tracer.info(f"[{cid}] No person_urn available. Using default branding.")
            person_urn = ""

        branding_config = BrandResolver.get_branding_config(person_urn)

        tracer.info(
            f"[{cid}] Branding resolved",
            extra={
                "person_urn": person_urn if person_urn else "default",
                "template_path": branding_config.template_path,
                "template_type": branding_config.template_type,
                "draw_profile": branding_config.draw_profile,
                "draw_name": branding_config.draw_name,
                "draw_role": branding_config.draw_role,
                "draw_badge": branding_config.draw_badge,
            }
        )

        # STEP 2: Render image with branding configuration
        tracer.info(f"[{cid}] STEP 2: Rendering image...")
        render_start = datetime.now()

        font_path = settings.FONTS_PATH + "Inter_18pt-SemiBold.ttf"
        profile_name = getattr(settings, "PROFILE_NAME", "")
        profile_role = getattr(settings, "PROFILE_ROLE", "")

        image_bytes = await render_linkedin_image(
            branding_config=branding_config,
            thought=thought,
            profile_name=profile_name,
            profile_role=profile_role,
            font_path=font_path,
            save_path=None  # Save in next step
        )

        render_elapsed = (datetime.now() - render_start).total_seconds()

        tracer.info(
            f"[{cid}] Image rendered successfully",
            extra={
                "image_bytes_length": len(image_bytes),
                "elapsed_s": render_elapsed
            }
        )

        if not image_bytes:
            tracer.error(f"[{cid}] Image rendering returned empty bytes")
            return {
                "image_bytes": None,
                "image_url": None,
                "image_rendered_at": False,
            }

        # STEP 3: Save to disk
        tracer.info(f"[{cid}] STEP 3: Saving image to disk...")

        output_dir = Path("assets/generated_images")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Include URN suffix for traceability
        urn_suffix = (person_urn.split(":")[-1][:8]) if person_urn else "default"
        image_path = output_dir / f"post_{post_id}_{urn_suffix}_{timestamp}.png"

        try:
            with open(image_path, "wb") as f:
                f.write(image_bytes)

            tracer.info(
                f"[{cid}] Image saved to disk",
                extra={
                    "image_path": str(image_path.absolute()),
                    "file_size": image_path.stat().st_size if image_path.exists() else 0
                }
            )
        except Exception as save_err:
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
            f"[{cid}] EXIT image_rendering_node - SUCCESS",
            extra={
                "image_url": str(image_path),
                "template": branding_config.template_path,
                "template_type": branding_config.template_type,
            }
        )

        return return_value

    except FileNotFoundError as e:
        tracer.error(
            f"[{cid}] Template file not found: {str(e)}",
            exc_info=True
        )
        # Graceful fallback - skip image
        tracer.info(f"[{cid}] Skipping image rendering (template not found)")
        return {
            "image_bytes": None,
            "image_url": None,
            "image_rendered_at": False,
        }

    except Exception as e:
        tracer.error(
            f"[{cid}] Exception in image_rendering_node_minimal",
            exc_info=True,
            extra={"error": str(e)}
        )
        # Graceful fallback - skip image
        tracer.info(f"[{cid}] Skipping image rendering (error occurred)")
        return {
            "image_bytes": None,
            "image_url": None,
            "image_rendered_at": False,
        }
