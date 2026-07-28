"""Free AI image generation using Pollinations.ai for testing."""
import logging
import urllib.parse

logger = logging.getLogger(__name__)

async def generate_post_image(topic: str) -> str:
    """Generate a free image for a post topic using Pollinations.ai.

    Args:
        topic: The post topic

    Returns:
        URL of the generated image

    Raises:
        Exception: If generation fails
    """
    try:
        logger.info(f"Generating FREE test image for topic: {topic[:50]}")
        
        # Create a professional prompt
        prompt = f"Professional, modern corporate tech illustration about: {topic}. Clean design, no text, high quality."
        
        # URL-encode the prompt so it can be passed safely in a web link
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Pollinations dynamically generates and returns a JPEG directly from this URL
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        
        logger.info(f"Free image URL generated successfully: {image_url}")
        
        return image_url

    except Exception as e:
        logger.error(f"Failed to generate free image for topic '{topic}': {str(e)}")
        raise