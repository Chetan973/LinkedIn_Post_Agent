"""Updated image rendering node using user-aware branding.

Orchestrates:
1. Fetch authenticated user profile from LinkedIn
2. Resolve branding configuration (per-user)
3. Render image with BrandingConfig
4. Save to disk

Never hardcodes user details.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.Services.image_renderer_v2 import render_linkedin_image_v2
from app.branding.profile_service import get_authenticated_profile
from app.branding.resolver import BrandResolver
from app.core.config import settings
from app.core.instrumentation import create_context_logger, get_correlation_id

logger = logging.getLogger(__name__)
tracer = create_context_logger(__name__)


async def image_rendering_node_v2(state: dict) -> dict:
    """Render LinkedIn image with user-aware branding.

    Workflow:
    1. Fetch authenticated user profile (using access token)
    2. Resolve branding configuration (per-user, never hardcoded)
    3. Render image using BrandingConfig
    4. Save to disk for LinkedIn upload

    Args:
        state: LangGraph state containing:
            - ai_thought: Generated thought (20-35 words, max 3 lines)
            - access_token: LinkedIn OAuth token (from authenticated user)
            - post_id: For file naming

    Returns:
        Updated state dict with:
            - image_bytes: PNG bytes (in-memory)
            - image_url: Local file path to saved PNG
            - image_size_bytes: File size in bytes
            - image_rendered_at: True if successful

    Raises:
        ValueError: If required state fields missing
        Exception: If rendering fails
    """
    cid = get_correlation_id()
    thought = state.get("ai_thought")
    post_id = state.get("post_id", "unknown")
    access_token = state.get("access_token")

    tracer.info(
        f"[{cid}] ENTER image_rendering_node_v2",
        extra={
            "post_id": post_id,
            "has_thought": bool(thought),
            "has_access_token": bool(access_token),
            "thought_preview": thought[:30] if thought else None
        }
    )

    # Validation
    if not thought:
        tracer.warning(f"[{cid}] No thought to render. Returning None image_url.")
        return {
            "image_bytes": None,
            "image_url": None,
            "image_rendered_at": False,
        }

    if not access_token:
        tracer.warning(
            f"[{cid}] No access token available. Cannot fetch user profile. Skipping image."
        )
        return {
            "image_bytes": None,
            "image_url": None,
            "image_rendered_at": False,
        }

    try:
        # STEP 1: Fetch authenticated user profile
        tracer.info(f"[{cid}] STEP 1: Fetching authenticated user profile from LinkedIn...")
        profile_start = datetime.now()

        profile = await get_authenticated_profile(access_token)

        profile_elapsed = (datetime.now() - profile_start).total_seconds()
        tracer.info(
            f"[{cid}] Profile fetched successfully",
            extra={
                "person_urn": profile.person_urn,
                "display_name": profile.display_name,
                "headline": profile.headline,
                "elapsed_s": profile_elapsed
            }
        )

        # STEP 2: Resolve branding configuration
        tracer.info(f"[{cid}] STEP 2: Resolving branding configuration...")
        branding_config = BrandResolver.resolve(profile)

        tracer.info(
            f"[{cid}] Branding resolved",
            extra={
                "person_urn": branding_config.person_urn,
                "display_name": branding_config.display_name,
                "template_path": branding_config.template_path,
                "has_profile_image": bool(branding_config.profile_image_url)
            }
        )

        # STEP 3: Render image using BrandingConfig
        tracer.info(f"[{cid}] STEP 3: Rendering image with BrandingConfig...")
        render_start = datetime.now()

        image_bytes = await render_linkedin_image_v2(
            branding_config=branding_config,
            thought=thought,
            save_path=None  # Save in step 4
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

        # STEP 4: Save to disk
        tracer.info(f"[{cid}] STEP 4: Saving image to disk...")

        output_dir = Path("assets/generated_images")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Include person_urn in filename for traceability
        urn_short = branding_config.person_urn.split(":")[-1][:8]  # Last 8 chars of URN
        image_path = output_dir / f"post_{post_id}_{urn_short}_{timestamp}.png"

        try:
            with open(image_path, "wb") as f:
                f.write(image_bytes)

            tracer.info(
                f"[{cid}] Image saved to disk",
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
            "branding_config": branding_config,  # Store for reference
        }

        tracer.info(
            f"[{cid}] EXIT image_rendering_node_v2 - SUCCESS",
            extra={
                "image_url": str(image_path),
                "person_urn": branding_config.person_urn,
                "display_name": branding_config.display_name
            }
        )

        return return_value

    except Exception as e:
        tracer.error(
            f"[{cid}] Exception in image_rendering_node_v2",
            exc_info=True,
            extra={"error": str(e)}
        )
        # Don't fail workflow - image is optional
        tracer.info(f"[{cid}] Returning None for image_url (proceeding without image)")
        return {
            "image_bytes": None,
            "image_url": None,
            "image_rendered_at": False,
        }
