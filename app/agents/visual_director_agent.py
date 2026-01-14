"""
Visual Director Agent
Generates optimized image search queries from slide content for stock photo APIs
"""

from typing import Dict, Any
from app.services.openai_service import generate_json_completion
from app.models.lesson_schema import BloomLevel, SlideType
import logging

logger = logging.getLogger(__name__)


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
                "keywords": [],
                "imageType": "none",
                "confidence": 0,
                "reasoning": "Summary slides typically don't need images"
            }
        
        system_message = """You are a Visual Content Director for educational materials.

Your job is to analyze slide content and create the PERFECT search query for stock photo APIs (Unsplash, Pexels).

CRITICAL RULES:
1. Queries must be 3-8 words maximum
2. Use simple, descriptive language
3. Focus on CONCRETE, PHOTOGRAPHABLE subjects (not abstract concepts)
4. Avoid text-heavy images (stock photos are better than diagrams with text)
5. Consider age-appropriateness for the grade level
6. Prefer nature, real-world examples, and clear visuals

ORIENTATION GUIDELINES:
- "landscape" for most content slides (16:9 ratio)
- "portrait" for people-focused or vertical subjects

IMAGE TYPE GUIDELINES:
- "stock_photo" for real-world subjects (90% of cases)
- "diagram" for process flows, cycles (e.g., water cycle diagram)
- "illustration" for abstract concepts that can't be photographed

Return JSON format:
{
  "imageQuery": "concise search query",
  "orientation": "landscape",
  "keywords": ["tag1", "tag2", "tag3"],
  "imageType": "stock_photo",
  "confidence": 85,
  "reasoning": "Brief explanation of choice"
}"""

        prompt = f"""Analyze this educational slide and generate the optimal image search query:

SLIDE DETAILS:
- Title: {slide_title}
- Content: {slide_content[:500]}  
- Subject: {subject}
- Grade Level: {grade_level}
- Bloom's Level: {getattr(bloom_level, 'value', bloom_level)}
- Slide Type: {getattr(slide_type, 'value', slide_type)}

Generate the perfect image search query for stock photo APIs."""

        try:
            result = await generate_json_completion(
                prompt=prompt,
                system_message=system_message,
                max_tokens=300,
                temperature=0.7
            )
            
            # Validate and set defaults
            query = result.get("imageQuery", "")
            
            # If query is empty or None, return low confidence
            if not query:
                logger.warning(f"No image query generated for slide: {slide_title}")
                return {
                    "imageQuery": None,
                    "orientation": "landscape",
                    "keywords": [],
                    "imageType": "none",
                    "confidence": 0,
                    "reasoning": "No suitable image found for this content"
                }
            
            return {
                "imageQuery": query,
                "orientation": result.get("orientation", "landscape"),
                "keywords": result.get("keywords", []),
                "imageType": result.get("imageType", "stock_photo"),
                "confidence": result.get("confidence", 75),
                "reasoning": result.get("reasoning", "Generated from slide content")
            }
            
        except Exception as e:
            logger.error(f"Visual Director failed for slide '{slide_title}': {e}")
            return {
                "imageQuery": None,
                "orientation": "landscape",
                "keywords": [],
                "imageType": "none",
                "confidence": 0,
                "reasoning": f"Error: {str(e)}"
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
