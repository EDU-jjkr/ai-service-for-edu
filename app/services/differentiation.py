"""
Differentiation Service for generating Support/Core/Extension lesson versions.

This service implements differentiated instruction by adapting lesson content
for different student ability levels while maintaining content coherence.
"""

from enum import Enum
from typing import Dict, List
import logging
import asyncio
from app.models.lesson_schema import LessonDeck, LessonMetadata, LearningStructure, Slide
from app.services.openai_service import stream_completion

logger = logging.getLogger(__name__)


class DifferentiationLevel(str, Enum):
    """Student ability levels for differentiated instruction."""
    SUPPORT = "SUPPORT"
    CORE = "CORE"
    EXTENSION = "EXTENSION"


class DifferentiationService:
    """
    Service for generating differentiated versions of lesson content.
    
    Differentiation Strategies:
    - SUPPORT: Simpler vocabulary, shorter content, lower Bloom's levels
    - CORE: Standard grade-level content (original)
    - EXTENSION: Advanced vocabulary, critical thinking, higher Bloom's levels
    """
    
    @staticmethod
    async def generate_differentiated_deck(
        core_deck: LessonDeck,
        target_level: DifferentiationLevel
    ) -> LessonDeck:
        """
        Generate a differentiated version of a lesson deck.
        
        Args:
            core_deck: The original core-level lesson deck
            target_level: SUPPORT or EXTENSION (CORE returns original)
            
        Returns:
            Differentiated LessonDeck with adapted content
        """
        if target_level == DifferentiationLevel.CORE:
            return core_deck  # No changes needed
        
        logger.info(f"Generating {target_level} version of deck: {core_deck.meta.topic}")
        
        # Extract metadata
        grade = core_deck.meta.grade
        subject = core_deck.meta.subject
        
        # Filter and differentiate slides based on Bloom's levels
        filtered_slides = DifferentiationService._filter_slides_by_bloom(
            core_deck.slides,
            target_level
        )
        
        # Differentiate each slide's content in parallel
        tasks = [
            DifferentiationService.differentiate_slide_content(
                slide=slide,
                target_level=target_level,
                grade=grade,
                subject=subject
            )
            for slide in filtered_slides
        ]
        
        differentiated_slides = await asyncio.gather(*tasks)
        
        # Update metadata
        new_meta = LessonMetadata(
            topic=f"{core_deck.meta.topic} ({target_level} Level)",
            grade=grade,
            subject=subject,
            standards=core_deck.meta.standards,
            theme=core_deck.meta.theme,
            pedagogical_model=core_deck.meta.pedagogical_model
        )
        
        # Update structure with new Bloom's progression
        new_structure = LearningStructure(
            learning_objectives=core_deck.structure.learning_objectives,
            vocabulary=core_deck.structure.vocabulary,
            prerequisites=core_deck.structure.prerequisites,
            bloom_progression=[s.bloom_level for s in differentiated_slides]
        )
        
        logger.info(f"✓ Generated {target_level} version with {len(differentiated_slides)} slides")
        
        return LessonDeck(
            meta=new_meta,
            structure=new_structure,
            slides=differentiated_slides
        )
    
    @staticmethod
    async def differentiate_slide_content(
        slide: Slide,
        target_level: DifferentiationLevel,
        grade: str,
        subject: str
    ) -> Slide:
        """
        Differentiate a single slide's content based on target level.
        
        Args:
            slide: Original slide object
            target_level: SUPPORT or EXTENSION
            grade: Grade level
            subject: Subject area
            
        Returns:
            Differentiated slide object
        """
        if target_level == DifferentiationLevel.CORE:
            return slide  # No changes
        
        original_content = slide.content
        title = slide.title
        bloom_level = slide.bloom_level
        
        # Generate differentiated content
        try:
            if target_level == DifferentiationLevel.SUPPORT:
                new_content = await DifferentiationService._generate_support_content(
                    title=title,
                    content=original_content,
                    grade=grade,
                    subject=subject
                )
            else:  # EXTENSION
                new_content = await DifferentiationService._generate_extension_content(
                    title=title,
                    content=original_content,
                    grade=grade,
                    subject=subject,
                    bloom_level=bloom_level
                )
            
            # Create a new slide object with updated content
            # We copy all fields but update content and speaker notes
            differentiated_slide = slide.model_copy(update={
                "content": new_content,
                "speakerNotes": DifferentiationService._generate_differentiation_note(
                    target_level, original_content, new_content
                )
            })
            
            return differentiated_slide
            
        except Exception as e:
            logger.error(f"Failed to differentiate slide '{title}': {e}")
            # Return original on error
            return slide
    
    @staticmethod
    async def _generate_support_content(
        title: str,
        content: str,
        grade: str,
        subject: str
    ) -> str:
        """Generate simplified content for SUPPORT level."""
        
        grade_num = int(grade) if grade.isdigit() else 8
        target_grade = max(1, grade_num - 2)  # 2 grades below
        
        prompt = f"""Rewrite this slide content for struggling learners (Grade {target_grade} level).

ORIGINAL TITLE: {title}
ORIGINAL CONTENT:
{content}

TRANSFORMATIONS REQUIRED:
1. Use simple, everyday words (no academic vocabulary)
2. Break down to 3 bullet points maximum
3. Make sentences short and clear
4. Add definitions in parentheses for any necessary technical terms
5. Use concrete, relatable examples
6. Focus on basic understanding only

EXAMPLE:
Original: "Photosynthesis is the biochemical process by which plants convert light energy into chemical energy."
Support: "Plants make their own food using sunlight. This is called photosynthesis (making food from light). The green parts of plants catch the sunlight."

Generate the SUPPORT level content (3 bullet points max):"""

        system_message = """You are an educational content adapter specializing in differentiated instruction.
Create accessible content for students who need extra support.
Use simple language, short sentences, and concrete examples."""

        # Collect streamed response
        chunks = []
        async for chunk in stream_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=250
        ):
            chunks.append(chunk)
        
        return ''.join(chunks).strip()
    
    @staticmethod
    async def _generate_extension_content(
        title: str,
        content: str,
        grade: str,
        subject: str,
        bloom_level: str
    ) -> str:
        """Generate advanced content for EXTENSION level."""
        
        grade_num = int(grade) if grade.isdigit() else 8
        target_grade = grade_num + 2  # 2 grades above
        
        prompt = f"""Rewrite this slide content for advanced learners (Grade {target_grade} level).

ORIGINAL TITLE: {title}
ORIGINAL CONTENT:
{content}

TRANSFORMATIONS  REQUIRED:
1. Use advanced vocabulary and technical terminology
2. Add depth and complexity to concepts
3. Include a critical thinking question requiring analysis or evaluation
4. Add a research challenge or extension activity
5. Make interdisciplinary connections where appropriate
6. Emphasize higher-order thinking (Bloom's: {bloom_level} or higher)

EXAMPLE:
Original: "Plants convert light energy into chemical energy through photosynthesis."
Extension: "Analyze the biochemical mechanisms of photosynthesis, comparing C3, C4, and CAM pathways. Critical Question: How might we engineer photosynthetic organisms for optimal efficiency in extreme environments? Research Challenge: Investigate artificial photosynthesis applications in renewable energy systems."

Generate the EXTENSION level content (include critical thinking question):"""

        system_message = """You are an educational content adapter specializing in differentiated instruction.
Create challenging content for advanced students that promotes critical thinking.
Use sophisticated vocabulary and complex concepts."""

        # Collect streamed response
        chunks = []
        async for chunk in stream_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=350
        ):
            chunks.append(chunk)
        
        return ''.join(chunks).strip()
    
    @staticmethod
    def _filter_slides_by_bloom(
        slides: List[Slide],
        level: DifferentiationLevel
    ) -> List[Slide]:
        """
        Filter slides based on Bloom's levels appropriate for differentiation level.
        
        Args:
            slides: List of slide objects
            level: Differentiation level
            
        Returns:
            Filtered list of slides
        """
        if level == DifferentiationLevel.SUPPORT:
            # Keep only lower-order Bloom's levels
            allowed_levels = ["REMEMBER", "UNDERSTAND"]
        elif level == DifferentiationLevel.EXTENSION:
            # Keep only higher-order Bloom's levels
            allowed_levels = ["APPLY", "ANALYZE", "EVALUATE", "CREATE"]
        else:  # CORE
            return slides  # No filtering
        
        filtered = [
            slide for slide in slides
            if slide.bloom_level in allowed_levels
        ]
        
        # Ensure minimum 2 slides
        if len(filtered) < 2:
            logger.warning(f"Only {len(filtered)} slides after Bloom's filtering, using first 5 from original")
            return slides[:5]
        
        logger.info(f"Filtered to {len(filtered)} slides for {level} level (Bloom's: {allowed_levels})")
        return filtered
    
    @staticmethod
    def _generate_differentiation_note(
        level: DifferentiationLevel,
        original_content: str,
        new_content: str
    ) -> str:
        """
        Generate a note explaining the differentiation applied.
        
        Args:
            level: Differentiation level applied
            original_content: Original slide content
            new_content: Differentiated content
            
        Returns:
            Note string
        """
        if level == DifferentiationLevel.SUPPORT:
            return f"SUPPORT Level: Simplified vocabulary and concepts for struggling learners. Focus on foundational understanding."
        elif level == DifferentiationLevel.EXTENSION:
            return f"EXTENSION Level: Advanced content with critical thinking challenges for gifted learners. Emphasizes higher-order skills."
        else:
            return "CORE Level: Standard grade-level content."


# Convenience function for singleton pattern (optional)
_differentiation_service = None

def get_differentiation_service() -> DifferentiationService:
    """Get singleton instance of DifferentiationService."""
    global _differentiation_service
    if _differentiation_service is None:
        _differentiation_service = DifferentiationService()
    return _differentiation_service
