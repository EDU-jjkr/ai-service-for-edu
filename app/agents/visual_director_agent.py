"""
Visual Director Agent
Generates optimized image search queries from slide content for stock photo APIs
"""

from typing import Dict, Any
from app.services.openai_service import generate_json_completion
from app.models.lesson_schema import BloomLevel, SlideType
import logging

logger = logging.getLogger(__name__)


def smart_truncate(text: str, max_length: int = 500) -> str:
    """
    Truncate text intelligently at sentence or word boundaries.
    
    Args:
        text: Text to truncate
        max_length: Maximum character length
        
    Returns:
        Truncated text that doesn't cut mid-sentence or mid-word
    """
    if len(text) <= max_length:
        return text
    
    # Try to find a sentence boundary (., !, ?) before max_length
    truncated = text[:max_length]
    
    # Look for sentence endings in reverse
    for delimiter in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
        last_sentence = truncated.rfind(delimiter)
        if last_sentence > max_length * 0.5:  # At least 50% of max_length
            return text[:last_sentence + 1].strip()
    
    # If no sentence boundary found, try word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.5:
        return text[:last_space].strip() + '...'
    
    # Fallback: hard truncate with ellipsis
    return text[:max_length].strip() + '...'


class VisualDirectorAgent:
    """
    Specialized agent for generating image search queries based on slide content.
    
    The Visual Director analyzes slide content, learning objectives, and Bloom's level
    to produce optimal search queries for stock photo APIs like Unsplash and Pexels.
    """
    
    @staticmethod
    async def generate_image_query(
        slide_content: str,
        slide_title: str,
        bloom_level: BloomLevel,
        subject: str,
        grade_level: str,
        slide_type: SlideType
    ) -> Dict[str, Any]:
        """
        Analyze slide and generate optimized image search query.
        
        Args:
            slide_content: The text content of the slide
            slide_title: Title of the slide
            bloom_level: Cognitive level (REMEMBER, UNDERSTAND, etc.)
            subject: Subject area (e.g., "Science", "Mathematics")
            grade_level: Grade level (e.g., "4", "8")
            slide_type: Type of slide (INTRODUCTION, CONCEPT, etc.)
            
        Returns:
            Dict containing:
            - imageQuery: Optimized search query string
            - orientation: "landscape" or "portrait"
            - keywords: List of relevant tags
            - imageType: "stock_photo", "diagram", or "illustration"
            - confidence: 0-100 score for using this image
        """
        
        # Skip image generation for certain slide types
        if slide_type == SlideType.SUMMARY:
            logger.info(f"Skipping image for SUMMARY slide: {slide_title}")
            return {
                "imageQuery": None,
                "orientation": "landscape",
                "imageType": "none"
            }
        
        system_message = """You are a Visual Content Director for educational materials.

Generate concise image search queries for stock photo APIs (Unsplash, Pexels).

RULES:
1. Keep queries 3-8 words, simple and descriptive
2. Focus on CONCRETE, PHOTOGRAPHABLE subjects
3. Prefer real-world examples and clear visuals
4. Consider age-appropriateness

Return STRICT JSON (no trailing commas, no commentary):
{
  "imageQuery": "concise search query",
  "orientation": "landscape",
  "imageType": "stock_photo"
}

orientation: "landscape" (default) or "portrait"
imageType: "stock_photo", "diagram", or "illustration" """

        prompt = f"""Generate an image search query for this slide:

Title: {slide_title}
Content: {smart_truncate(slide_content, 500)}
Subject: {subject}
Grade: {grade_level}
Bloom Level: {bloom_level.value}
Slide Type: {slide_type.value}"""

        try:
            result = await generate_json_completion(
                prompt=prompt,
                system_message=system_message,
                max_tokens=300,
                temperature=0.7
            )
            
            # Log raw result for debugging
            logger.debug(f"Visual Director raw result for '{slide_title}': {result}")
            
            # Validate required keys
            query = result.get("imageQuery")
            
            if not query:
                logger.warning(
                    f"No imageQuery in result for slide '{slide_title}' (type: {slide_type.value}). "
                    f"Raw result keys: {list(result.keys())}"
                )
                return {
                    "imageQuery": None,
                    "orientation": "landscape",
                    "imageType": "none"
                }
            
            # Success - log for monitoring
            logger.info(f"✓ Image query for '{slide_title}': \"{query}\"")
            
            return {
                "imageQuery": query,
                "orientation": result.get("orientation", "landscape"),
                "imageType": result.get("imageType", "stock_photo")
            }
            
        except KeyError as e:
            logger.error(
                f"Missing key in Visual Director result for '{slide_title}': {e}. "
                f"Raw result: {result if 'result' in locals() else 'N/A'}"
            )
            return {
                "imageQuery": None,
                "orientation": "landscape",
                "imageType": "none"
            }
        except Exception as e:
            logger.error(
                f"Visual Director failed for slide '{slide_title}' (type: {slide_type.value}): {type(e).__name__}: {e}"
            )
            return {
                "imageQuery": None,
                "orientation": "landscape",
                "imageType": "none"
            }
    
    @staticmethod
    async def batch_generate_queries(slides_data: list) -> list:
        """
        Generate image queries for multiple slides in sequence.
        
        Args:
            slides_data: List of dicts with keys: content, title, bloom_level, subject, grade_level, slide_type
            
        Returns:
            List of image query results in same order as input
        """
        results = []
        
        for slide in slides_data:
            result = await VisualDirectorAgent.generate_image_query(
                slide_content=slide.get("content", ""),
                slide_title=slide.get("title", ""),
                bloom_level=slide.get("bloom_level", BloomLevel.REMEMBER),
                subject=slide.get("subject", ""),
                grade_level=slide.get("grade_level", ""),
                slide_type=slide.get("slide_type", SlideType.CONCEPT)
            )
            results.append(result)
        
        # Log statistics
        with_images = sum(1 for r in results if r.get("imageQuery"))
        logger.info(f"Visual Director: {with_images}/{len(slides_data)} slides will have images")
        
        return results
