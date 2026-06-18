from fastapi import APIRouter, HTTPException
from app.models.schemas import DeckGenerateRequest, DeckGenerateResponseLegacy, Slide, VisualMetadata
from app.models.modify_schemas import DeckModifyRequest
from app.services.openai_service import generate_json_completion
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate-topic", response_model=DeckGenerateResponseLegacy)
async def generate_topic(request: DeckGenerateRequest):
    """Generate a topic outline using AI with smart visual routing and generation"""
    try:
        # Enhanced system message with instructional design expertise
        system_message = """You are an elite instructional designer and master teacher with expertise in creating comprehensive topic outlines. You understand learning science, cognitive load theory, and how to structure information for maximum retention.

Your topic outlines are known for:
- Clear narrative flow that builds understanding step-by-step
- Perfect balance between content depth and visual clarity
- Age-appropriate language and examples that resonate with students
- Engaging hooks and memorable takeaways
- Strategic use of questions, examples, and applications
- Content formatted for visual presentation (not essays)

You create topic content that teachers can directly use with minimal editing. Each section is focused, visually presentable, and designed to facilitate discussion rather than being read verbatim.

Always respond with valid, well-structured JSON."""

        # Calculate recommended section allocation
        intro_sections = 1
        conclusion_sections = 1
        content_sections = request.numSlides - 2
        
        prompt = f"""Design a comprehensive topic outline with exceptional pedagogical structure.

TOPIC OUTLINE SPECIFICATIONS:
- Topic: "{request.topic}"
- Subject: {request.subject}
- Grade Level: {request.gradeLevel}
- Total Sections: {request.numSlides} (including intro and conclusion)

INSTRUCTIONAL DESIGN FRAMEWORK:

1. NARRATIVE STRUCTURE:
   - Section 1: Hook + Learning Objectives (What will students discover?)
   - Sections 2-{content_sections + 1}: Core content with logical progression
   - Section {request.numSlides}: Summary + Key Takeaways

2. COGNITIVE LOAD PRINCIPLES:
   - Each section should focus on ONE main idea
   - Use 3-5 concise bullet points OR 2-3 short paragraphs per section
   - Break complex concepts across multiple sections rather than cramming
   - Include transition phrases between concepts

3. CONTENT REQUIREMENTS PER SECTION:

   **Introduction Section (Section 1):**
   - Compelling hook/question that sparks curiosity
   - 2-4 clear learning objectives starting with action verbs
   - Optional: Relevant real-world connection

   **Content Sections (Sections 2-{content_sections + 1}):**
   - Clear, specific title (not generic like "Main Concept")
   - 3-5 bullet points OR 2-3 short paragraphs
   - Each point should be presentation-ready (concise, not full sentences unless needed)
   - Include at least 2 sections with concrete examples or applications
   - Progressive complexity: start simple, build to more sophisticated ideas
   - Add discussion prompts or activities where appropriate

   **Summary Section (Final Section):**
   - 3-4 key takeaways (what students should remember)
   - Brief recap of main concepts covered
   - NO questions - this is purely a summary

4. AGE-APPROPRIATE ADAPTATION FOR {request.gradeLevel}:
   - Vocabulary and sentence complexity suitable for this grade
   - Examples and references relevant to students' lives and interests
   - Appropriate cognitive expectations (concrete vs. abstract thinking)
   - Engagement strategies matching attention span and maturity

5. SUBJECT-SPECIFIC CONSIDERATIONS FOR {request.subject}:
   - Use discipline-appropriate terminology and frameworks
   - Include relevant examples from the field
   - Consider what visuals or diagrams might accompany content (mention in brackets if helpful)

6. ENGAGEMENT ELEMENTS (distribute across outline):
   - At least 1 real-world application or example
   - At least 1 thought experiment or "what if" scenario  
   - Use "you" language to directly address students

OUTPUT FORMAT (return as JSON):
{{
    "title": "Engaging, specific topic title (not just the topic)",
    "slides": [
        {{
            "title": "Specific, Clear Section Title",
            "content": "• Bullet point 1: Concise, presentation-ready text
• Bullet point 2: Use formatting like bold **terms** or [Visual: diagram suggestion]
• Bullet point 3: Each point is digestible and focused
• Bullet point 4: Include examples, not just definitions
• Optional 5th point if needed

OR for conceptual sections:

Opening paragraph that introduces the concept clearly.

Second paragraph that provides example or elaboration. Keep paragraphs short (2-4 sentences max).

[Optional note about visuals, activities, or discussion prompts]",
            "order": 1
        }},
        {{
            "title": "Next Section Title",
            "content": "Content for section 2...",
            "order": 2
        }}
    ]
}}

CRITICAL QUALITY STANDARDS:
- Each section must be teachable in 2-4 minutes of class time
- Content should prompt discussion, not just be read aloud
- Use specific examples, not abstract generalities
- Maintain consistent depth appropriate to {request.gradeLevel}
- Ensure logical flow where each section builds on previous ones
- Avoid information overload - less is more
- Write for presentation, not for reading (visual-friendly format)
- Include exactly {request.numSlides} sections, properly numbered 1-{request.numSlides}
- DO NOT include practice questions or Q&A slides - this is for teaching content only

CONTENT STRUCTURE CHECKLIST:
✓ Section 1: Engaging intro with clear objectives
✓ Early sections: Foundational concepts and definitions
✓ Middle sections: Development, examples, applications
✓ Later sections: Advanced concepts, real-world connections
✓ Final section: Concise summary of key takeaways (NO questions)

Generate the complete {request.numSlides}-section topic outline now. Make it engaging, clear, and immediately usable for classroom teaching."""

        # Step 1: Generate section text content
        logger.info(f"Generating topic for: {request.topic}, subject: {request.subject}")
        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=3000,
            temperature=0.7
        )

        # Validate section count matches request
        if len(result["slides"]) != request.numSlides:
            logger.warning(f"Generated {len(result['slides'])} sections but {request.numSlides} were requested")

        enriched_slides = [
            Slide(
                title=slide_data["title"],
                content=slide_data["content"],
                order=slide_data["order"],
            )
            for slide_data in result["slides"]
        ]

        logger.info(f"Topic generation complete: {len(enriched_slides)} sections")

        return DeckGenerateResponseLegacy(
            title=result["title"],
            slides=enriched_slides
        )

    except Exception as e:
        logger.error(f"Topic generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate topic: {str(e)}")


@router.post("/modify-topic", response_model=DeckGenerateResponseLegacy)
async def modify_topic(request: DeckModifyRequest):
    """Modify an existing topic outline based on user feedback"""
    try:
        current_topic_json = json.dumps(request.currentDeck, indent=2)
        
        system_message = """You are an expert instructional designer revising a topic outline based on teacher feedback. 
        You will receive the current JSON of the topic and specific instructions for changes.
        Return the FULLY updated JSON structure, maintaining the valid schema."""

        prompt = f"""REVISE THIS TOPIC OUTLINE.

        CONTEXT:
        Subject: {request.subject}
        Grade: {request.gradeLevel}

        USER FEEDBACK / INSTRUCTIONS:
        "{request.feedback}"

        CURRENT TOPIC JSON:
        {current_topic_json}

        TASK:
        1. Apply the user's feedback to the topic outline.
        2. Keep the same structure (Title, Slides list).
        3. If sections need to be added/removed/edited, do so.
        4. Return the COMPLETE updated JSON.
        """

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=3000,
            temperature=0.7
        )
        
        updated_slides = [
            Slide(
                title=slide_data.get("title", "Untitled"),
                content=slide_data.get("content", ""),
                order=slide_data.get("order", 0),
            )
            for slide_data in result.get("slides", [])
        ]

        return DeckGenerateResponseLegacy(
            title=result.get("title", request.currentDeck.get("title")),
            slides=updated_slides
        )

    except Exception as e:
        logger.error(f"Topic modification failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to modify topic: {str(e)}")
