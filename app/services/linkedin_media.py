"""LinkedIn 3-step media asset upload pipeline using modern REST API."""

import logging
import httpx
import time
import asyncio
from pathlib import Path
from typing import Tuple, Optional
from urllib.parse import quote
from app.core.instrumentation import (
    create_context_logger,
    instrument_async_function,
    log_async_operation,
    log_http_request,
    log_http_response,
    get_correlation_id,
)

logger = logging.getLogger(__name__)
tracer = create_context_logger(__name__)


class LinkedInMediaUploader:
    """Handles LinkedIn's 3-step media upload API for image posts using /rest/images."""

    def __init__(self, access_token: str):
        """Initialize with LinkedIn access token.

        Args:
            access_token: LinkedIn OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202606",
        }

    def _format_urn(self, person_urn: str) -> str:
        """Ensure URN has correct 'urn:li:person:' prefix."""
        if person_urn.startswith("urn:li:person:") or person_urn.startswith("urn:li:organization:"):
            return person_urn
        return f"urn:li:person:{person_urn}"

    async def register_upload(self, person_urn: str) -> Tuple[str, str]:
        """Step 1: Initialize upload and receive presigned URL and image URN.

        Args:
            person_urn: LinkedIn person or organization URN

        Returns:
            Tuple of (upload_url, image_urn)
        """
        cid = get_correlation_id()
        tracer.info(
            f"[{cid}] ENTER register_upload",
            extra={"person_urn": person_urn}
        )

        owner_urn = self._format_urn(person_urn)
        url = "https://api.linkedin.com/rest/images?action=initializeUpload"
        payload = {
            "initializeUploadRequest": {
                "owner": owner_urn
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Log request
                log_http_request(
                    method="POST",
                    url=url,
                    headers=self.headers,
                    payload=payload
                )

                start_time = time.time()
                response = await client.post(url, headers=self.headers, json=payload)
                elapsed_ms = int((time.time() - start_time) * 1000)

                # DEBUG: Print raw initializeUpload response to stdout
                print("=" * 80)
                print("INITIALIZE UPLOAD RAW TEXT")
                print(response.text)
                print("=" * 80)

                # DEBUG: Print parsed JSON object to stdout
                print("=" * 80)
                print("PARSED JSON")
                print(f"Type: {type(response.json())}")
                print(response.json())
                print("=" * 80)

                # DEBUG: Log raw initializeUpload response
                logger.info("========== LinkedIn initializeUpload Response ==========")
                logger.info(f"Status: {response.status_code}")
                logger.info(f"Headers: {dict(response.headers)}")
                logger.info(f"Body: {response.text}")
                logger.info("=======================================================")

                # Log response
                log_http_response(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.text,
                    elapsed_ms=elapsed_ms
                )

                if response.status_code not in (200, 201):
                    tracer.error(
                        f"[{cid}] Failed to register upload: {response.status_code}",
                        extra={
                            "status": response.status_code,
                            "body": response.text[:500]
                        }
                    )
                    raise Exception(f"Initialize upload failed: {response.status_code} - {response.text}")

                data = response.json()
                if "value" in data:
                    data = data["value"]

                upload_url = data.get("uploadUrl")
                image_urn = data.get("image")

                # DEBUG: Print actual image_urn value to stdout (not logger)
                print("=" * 80)
                print("IMAGE URN FROM initializeUpload")
                print(f"Value: {repr(image_urn)}")
                print(f"Type: {type(image_urn)}")
                print(f"Length: {len(image_urn) if image_urn else 'None'}")
                print("=" * 80)

                # DEBUG: Log actual values returned
                logger.info(f"[{cid}] DEBUG - register_upload response:")
                logger.info(f"[{cid}]   image_urn: {image_urn}")
                logger.info(f"[{cid}]   image_urn type: {type(image_urn).__name__}")
                logger.info(f"[{cid}]   upload_url: {upload_url[:50] if upload_url else None}...")
                tracer.info(
                    f"[{cid}] DEBUG register_upload response",
                    extra={
                        "image_urn": image_urn,
                        "image_urn_type": type(image_urn).__name__,
                        "has_upload_url": bool(upload_url)
                    }
                )

                if not upload_url or not image_urn:
                    tracer.error(
                        f"[{cid}] Missing fields in response",
                        extra={
                            "has_upload_url": bool(upload_url),
                            "has_image_urn": bool(image_urn),
                            "response": data
                        }
                    )
                    raise Exception(f"Response missing uploadUrl or image: {data}")

                tracer.info(
                    f"[{cid}] EXIT register_upload success",
                    extra={
                        "image_urn": image_urn,
                        "upload_url_preview": upload_url[:50]
                    }
                )
                return upload_url, image_urn

            except Exception as e:
                tracer.error(
                    f"[{cid}] EXCEPTION register_upload: {str(e)}",
                    exc_info=True
                )
                raise

    async def wait_for_image_available(
        self,
        image_urn: str,
        max_retries: int = 30,
        retry_delay: float = 1.0,
    ) -> bool:
        """Step 2.5: Poll image status until AVAILABLE or timeout.

        CRITICAL: LinkedIn Image API requires polling after binary upload.
        Image must reach AVAILABLE status before being used in POST /rest/posts.

        Args:
            image_urn: Image URN from initialization step
            max_retries: Maximum polling attempts (30 retries = ~30+ seconds)
            retry_delay: Initial delay between retries (exponential backoff)

        Returns:
            True if AVAILABLE, raises exception if PROCESSING_FAILED or timeout
        """
        cid = get_correlation_id()
        tracer.info(
            f"[{cid}] ENTER wait_for_image_available - Polling for image status",
            extra={"image_urn": image_urn, "max_retries": max_retries}
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_retries):
                try:
                    # DEBUG: Compare raw vs encoded URLs
                    # But start with raw URL to establish baseline
                    encoded_urn = quote(image_urn, safe="")
                    url_raw = f"https://api.linkedin.com/rest/images/{image_urn}"
                    url_encoded = f"https://api.linkedin.com/rest/images/{encoded_urn}"

                    # Use RAW URL for first test (change only one variable)
                    url = url_raw

                    # DEBUG: Character analysis - check for hidden whitespace/control chars
                    if attempt == 0:
                        print("=" * 80)
                        print("IMAGE URN CHARACTER ANALYSIS")
                        print(f"Length: {len(image_urn)}")
                        for i, c in enumerate(image_urn):
                            print(f"  [{i:2d}] {repr(c):8s} ord={ord(c):3d} {chr(ord(c)) if 32 <= ord(c) < 127 else '[control]'}")
                        print("=" * 80)

                    # DEBUG: Inspect image_urn value in detail
                    if attempt == 0:
                        print("=" * 80)
                        print("URL ENCODING TEST")
                        print(f"Raw URN:       {repr(image_urn)}")
                        print(f"Encoded URN:   {repr(encoded_urn)}")
                        print(f"Raw URL:       {url_raw}")
                        print(f"Encoded URL:   {url_encoded}")
                        print(f"Using:         {url}")
                        print(f"Needs encoding: {image_urn != encoded_urn}")
                        print("=" * 80)
                        logger.info("========== DEBUG: Image URN Inspection ==========")
                        logger.info(f"1. Exact image_urn value: {image_urn}")
                        logger.info(f"2. repr(image_urn): {repr(image_urn)}")
                        logger.info(f"3. len(image_urn): {len(image_urn) if image_urn else 'None'}")
                        logger.info(f"4. image_urn.encode(): {image_urn.encode() if image_urn else 'None'}")
                        logger.info(f"5. Exact URL before request: {url}")

                        # Check if special characters need escaping
                        if image_urn:
                            quoted_urn = quote(image_urn, safe="")
                            logger.info(f"6. urllib.parse.quote(image_urn, safe=''): {quoted_urn}")
                            logger.info(f"7. Needs escaping: {image_urn != quoted_urn}")
                            if image_urn != quoted_urn:
                                logger.info(f"   Differences:")
                                logger.info(f"   Original: {image_urn}")
                                logger.info(f"   Quoted:   {quoted_urn}")

                        logger.info("==================================================")

                        tracer.info(
                            f"[{cid}] DEBUG image URN inspection",
                            extra={
                                "image_urn": image_urn,
                                "image_urn_type": type(image_urn).__name__,
                                "image_urn_len": len(image_urn) if image_urn else None,
                                "needs_escaping": image_urn != quote(image_urn, safe="") if image_urn else None,
                                "url": url
                            }
                        )

                    tracer.info(
                        f"[{cid}] Polling image status (attempt {attempt + 1}/{max_retries})",
                        extra={"image_urn": image_urn}
                    )

                    log_http_request(
                        method="GET",
                        url=url,
                        headers=self.headers,
                    )

                    poll_start = time.time()
                    response = await client.get(url, headers=self.headers, timeout=30.0)
                    poll_elapsed = int((time.time() - poll_start) * 1000)

                    # DEBUG: Log what httpx actually sent and received
                    if attempt == 0:
                        logger.info("========== DEBUG: HTTP Request/Response ==========")
                        logger.info(f"Final URL sent: {response.request.url}")
                        logger.info(f"Request method: {response.request.method}")
                        logger.info(f"Response status: {response.status_code}")
                        logger.info(f"Response text: {response.text}")
                        logger.info("==================================================")

                    log_http_response(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body=response.text,
                        elapsed_ms=poll_elapsed
                    )

                    if response.status_code != 200:
                        tracer.error(
                            f"[{cid}] Poll request failed",
                            extra={
                                "status": response.status_code,
                                "body": response.text[:500]
                            }
                        )
                        raise Exception(f"Poll failed: {response.status_code} - {response.text}")

                    data = response.json()
                    if "value" in data:
                        data = data["value"]

                    status = data.get("status")

                    tracer.info(
                        f"[{cid}] Image status: {status}",
                        extra={
                            "status": status,
                            "attempt": attempt + 1,
                            "image_urn": image_urn
                        }
                    )

                    # Check status
                    if status == "AVAILABLE":
                        tracer.info(
                            f"[{cid}] EXIT wait_for_image_available - Image AVAILABLE",
                            extra={"attempts": attempt + 1}
                        )
                        return True

                    if status == "PROCESSING_FAILED":
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown"
                        tracer.error(
                            f"[{cid}] Image processing failed",
                            extra={"error": error_msg}
                        )
                        raise Exception(f"Image processing failed: {error_msg}")

                    # Status is PROCESSING or other - wait and retry
                    if attempt < max_retries - 1:
                        tracer.info(
                            f"[{cid}] Image still PROCESSING, waiting before retry",
                            extra={"delay_ms": int(retry_delay * 1000)}
                        )
                        await asyncio.sleep(retry_delay)
                        # Exponential backoff, but cap at 5 seconds
                        retry_delay = min(retry_delay * 1.5, 5.0)

                except Exception as e:
                    if "PROCESSING_FAILED" in str(e) or "failed" in str(e).lower():
                        # Fatal error, don't retry
                        tracer.error(
                            f"[{cid}] Fatal error in image polling",
                            exc_info=True
                        )
                        raise

                    # Transient error, retry
                    if attempt == max_retries - 1:
                        tracer.error(
                            f"[{cid}] Image polling timeout after {max_retries} attempts",
                            exc_info=True
                        )
                        raise TimeoutError(f"Image did not reach AVAILABLE status after {max_retries} polls")

                    tracer.warning(
                        f"[{cid}] Transient error in polling, will retry",
                        extra={"error": str(e), "attempt": attempt + 1}
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 5.0)

            # Should not reach here
            tracer.error(f"[{cid}] Unexpected: polling loop exhausted")
            raise TimeoutError("Image polling loop exhausted")

    async def upload_image(self, upload_url: str, image_url: str) -> bool:
        """Step 2: Read generated image and upload to LinkedIn presigned URL.

        Args:
            upload_url: Presigned URL from initializeUpload step
            image_url: Local file path or URL to the generated image

        Returns:
            True if upload succeeded

        Raises:
            Exception: If file read or upload fails
        """
        cid = get_correlation_id()
        tracer.info(
            f"[{cid}] ENTER upload_image",
            extra={"image_url_preview": image_url[:50]}
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Read image binary (handle both local paths and URLs)
                tracer.info(f"[{cid}] Reading image from: {image_url}")
                image_path = Path(image_url)

                image_bytes = None
                if image_path.exists():
                    # Local file path (Windows: assets\generated_images\..., Unix: assets/generated_images/...)
                    tracer.info(
                        f"[{cid}] Reading from local file",
                        extra={"path": str(image_path.absolute())}
                    )
                    try:
                        with open(image_path, "rb") as f:
                            image_bytes = f.read()
                        tracer.info(
                            f"[{cid}] Read local image",
                            extra={"size_bytes": len(image_bytes)}
                        )
                    except FileNotFoundError as fnf_err:
                        tracer.error(
                            f"[{cid}] Image file not found",
                            exc_info=True,
                            extra={"path": str(image_path.absolute())}
                        )
                        raise Exception(f"Image file not found: {image_path}") from fnf_err
                    except IOError as io_err:
                        tracer.error(
                            f"[{cid}] Failed to read image file",
                            exc_info=True
                        )
                        raise Exception(f"Failed to read image file: {image_path}") from io_err
                else:
                    # Try as URL (for remote images)
                    tracer.info(
                        f"[{cid}] Image path doesn't exist locally, treating as URL",
                        extra={"url": image_url}
                    )
                    log_http_request(
                        method="GET",
                        url=image_url,
                    )
                    start_time = time.time()
                    img_resp = await client.get(image_url, timeout=30.0)
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    log_http_response(
                        status_code=img_resp.status_code,
                        headers=dict(img_resp.headers),
                        body=None,  # Don't log binary content
                        elapsed_ms=elapsed_ms
                    )

                    if img_resp.status_code != 200:
                        tracer.error(
                            f"[{cid}] Failed to download image from URL",
                            extra={"status": img_resp.status_code}
                        )
                        raise Exception(f"Failed to download source image: {img_resp.status_code}")

                    image_bytes = img_resp.content
                    tracer.info(
                        f"[{cid}] Downloaded image from URL",
                        extra={"size_bytes": len(image_bytes)}
                    )

                if not image_bytes:
                    tracer.error(f"[{cid}] Image bytes are empty")
                    raise Exception("Image bytes are empty after reading")

                tracer.info(
                    f"[{cid}] Image ready for upload",
                    extra={"size_bytes": len(image_bytes)}
                )

                # Upload binary data to LinkedIn presigned upload URL
                # NOTE: Presigned URL is from AWS/Azure - do NOT include LinkedIn auth header
                # LinkedIn provides time-limited credentials in the URL itself

                # Detect MIME type from image signature (not hardcoded)
                mime_type = "image/png"  # default
                if image_bytes.startswith(b'\x89PNG'):
                    mime_type = "image/png"
                elif image_bytes.startswith(b'\xff\xd8\xff'):
                    mime_type = "image/jpeg"
                elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
                    mime_type = "image/gif"

                logger.info(f"[{cid}] Detected MIME type: {mime_type}")

                put_headers = {
                    "Content-Type": mime_type,
                }
                tracer.info(
                    f"[{cid}] Uploading to LinkedIn presigned URL",
                    extra={
                        "size_bytes": len(image_bytes),
                        "url_preview": upload_url[:50]
                    }
                )

                log_http_request(
                    method="PUT",
                    url=upload_url,
                    headers=put_headers,
                )

                start_time = time.time()
                upload_resp = await client.put(upload_url, headers=put_headers, content=image_bytes)
                elapsed_ms = int((time.time() - start_time) * 1000)

                log_http_response(
                    status_code=upload_resp.status_code,
                    headers=dict(upload_resp.headers),
                    body=upload_resp.text,
                    elapsed_ms=elapsed_ms
                )

                tracer.info(
                    f"[{cid}] Upload response received",
                    extra={"status": upload_resp.status_code}
                )

                if upload_resp.status_code not in (200, 201, 204):
                    tracer.error(
                        f"[{cid}] Failed to upload binary image data",
                        extra={
                            "status": upload_resp.status_code,
                            "body": upload_resp.text[:500]
                        }
                    )
                    raise Exception(
                        f"Upload binary failed: {upload_resp.status_code} - {upload_resp.text}"
                    )

                tracer.info(f"[{cid}] EXIT upload_image success")
                return True

            except Exception as e:
                tracer.error(
                    f"[{cid}] EXCEPTION upload_image",
                    exc_info=True
                )
                raise

    def create_post_payload_with_image(
        self,
        text: str,
        image_urn: str,
        person_urn: str,
    ) -> dict:
        """Step 3: Build modern REST payload for creating an image post.

        Args:
            text: Post commentary text
            image_urn: Image URN returned from registration (urn:li:image:...)
            person_urn: LinkedIn person/organization URN

        Returns:
            Payload formatted for https://api.linkedin.com/rest/posts

        Note:
            For /rest/posts endpoint, content.media MUST be a dictionary,
            not an array. Structure: {"media": {"id": image_urn}}
        """
        if not image_urn:
            raise ValueError("Image URN is required for image post payload")

        owner_urn = self._format_urn(person_urn)
        payload = {
            "author": owner_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED",
            "content": {
                "media": {
                    "id": image_urn
                }
            }
        }

        logger.info(f"Created image post payload with URN: {image_urn}")
        return payload


async def upload_image_to_linkedin(
    image_url: str,
    post_text: str,
    access_token: str,
    person_urn: str,
) -> Tuple[dict, str]:
    """End-to-end LinkedIn image upload pipeline helper.

    Args:
        image_url: URL of image to upload
        post_text: Post commentary text
        access_token: LinkedIn OAuth access token
        person_urn: LinkedIn person URN

    Returns:
        Tuple of (post_payload, image_urn)
    """
    cid = get_correlation_id()
    tracer.info(
        f"[{cid}] ENTER upload_image_to_linkedin (PIPELINE)",
        extra={
            "image_url_preview": image_url[:50],
            "person_urn": person_urn
        }
    )

    uploader = LinkedInMediaUploader(access_token)

    try:
        # Step 1: Initialize upload
        tracer.info(f"[{cid}] STEP 1/3: Initializing upload...")
        upload_url, image_urn = await uploader.register_upload(person_urn)
        tracer.info(
            f"[{cid}] STEP 1/3 COMPLETE",
            extra={"image_urn": image_urn}
        )

        # Step 2: Upload binary image data
        tracer.info(f"[{cid}] STEP 2/3: Uploading binary image data...")
        upload_result = await uploader.upload_image(upload_url, image_url)
        tracer.info(
            f"[{cid}] STEP 2/3 COMPLETE",
            extra={"upload_result": upload_result}
        )

        if not upload_result:
            tracer.error(f"[{cid}] Upload returned False/None")
            raise Exception("Image upload returned False")

        # Step 2.5: Brief delay for LinkedIn processing
        # Member tokens cannot use GET /rest/images (permission restricted to w_member_social)
        # So we skip polling and give LinkedIn a moment to process the upload
        tracer.info(f"[{cid}] STEP 2.5/3: Waiting for LinkedIn to process upload...")
        await asyncio.sleep(2)
        tracer.info(
            f"[{cid}] STEP 2.5/3 COMPLETE - Proceeding to post creation",
            extra={"image_urn": image_urn}
        )

        # Step 3: Build post payload
        tracer.info(f"[{cid}] STEP 3/3: Building post payload...")
        post_payload = uploader.create_post_payload_with_image(post_text, image_urn, person_urn)
        tracer.info(
            f"[{cid}] STEP 3/3 COMPLETE",
            extra={
                "payload_keys": list(post_payload.keys()),
                "has_content": "content" in post_payload
            }
        )

        tracer.info(
            f"[{cid}] EXIT upload_image_to_linkedin success",
            extra={"image_urn": image_urn}
        )
        return post_payload, image_urn

    except Exception as e:
        tracer.error(
            f"[{cid}] EXCEPTION upload_image_to_linkedin",
            exc_info=True
        )
        raise