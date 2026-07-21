import httpx
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

LINKEDIN_API_URL = "https://api.linkedin.com/rest/posts"


class LinkedInRateLimitError(Exception):
    """Raised when LinkedIn rate limit is hit."""
    pass


class LinkedInServerError(Exception):
    """Raised on LinkedIn server errors (5xx)."""
    pass


@retry(
    stop=stop_after_attempt(settings.LINKEDIN_MAX_RETRIES),
    wait=wait_exponential(
        multiplier=settings.LINKEDIN_RETRY_BACKOFF,
        min=1,
        max=60
    ),
    retry=retry_if_exception_type((LinkedInServerError, httpx.TimeoutException)),
)
async def publish_to_linkedin(content: str) -> dict:
    """Publishes a text post to LinkedIn with automatic retry on transient errors.

    Retries on:
    - Server errors (5xx)
    - Timeout exceptions

    Raises:
    - LinkedInRateLimitError: When rate limit (429) is hit
    - Exception: For client errors (4xx except 429) that are not retryable
    """
    if not settings.LINKEDIN_ACCESS_TOKEN or not settings.LINKEDIN_PERSON_URN:
        raise ValueError("LinkedIn credentials are not properly configured in environment variables.")

    headers = {
        "Authorization": f"Bearer {settings.LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202606"
    }

    payload = {
        "author": settings.LINKEDIN_PERSON_URN,
        "commentary": content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(LINKEDIN_API_URL, headers=headers, json=payload)

            if response.status_code in [200, 201]:
                linkedin_post_id = response.headers.get("x-restli-id")
                logger.info(f"Successfully published to LinkedIn. Post ID: {linkedin_post_id}")
                return {
                    "status": "success",
                    "linkedin_post_id": linkedin_post_id
                }

            elif response.status_code == 429:
                retry_after = int(response.headers.get("retry-after", 60))
                logger.warning(f"LinkedIn rate limit hit. Retry after {retry_after}s")
                raise LinkedInRateLimitError(
                    f"Rate limited. Retry after {retry_after}s. Response: {response.text}"
                )

            elif 500 <= response.status_code < 600:
                logger.error(f"LinkedIn server error {response.status_code}: {response.text}")
                raise LinkedInServerError(f"LinkedIn server error {response.status_code}: {response.text}")

            else:
                logger.error(f"LinkedIn API error {response.status_code}: {response.text}")
                raise Exception(f"Failed to publish to LinkedIn: {response.status_code} - {response.text}")

        except httpx.TimeoutException as e:
            logger.warning(f"LinkedIn API timeout: {str(e)}")
            raise
        except LinkedInRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing to LinkedIn: {str(e)}")
            raise