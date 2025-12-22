from fastapi import APIRouter, HTTPException
from app.models.schemas import DeckGenerateRequest, DeckGenerateResponse, Slide, VisualMetadata
from app.models.modify_schemas import DeckModifyRequest
from app.services.openai_service import generate_json_completion
from app.services.visual_routing import batch_route_slides
from app.services.visual_generator import batch_generate_visuals
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

# ... (generate_deck function stays here, simplified for brevity in this replace block if not editing it) ...

@router.post("/modify-deck", response_model=DeckGenerateResponse)
async def modify_deck(request: DeckModifyRequest):
    """Modify an existing deck based on user feedback"""
    try:
        current_deck_json = json.dumps(request.currentDeck, indent=2)
        
        system_message = """You are an expert instructional designer revising a presentation deck based on teacher feedback. 
        You will receive the current JSON of the deck and specific instructions for changes.
        Return the FULLY updated JSON structure, maintaining the valid schema."""

        prompt = f"""REVIESE THIS DECK.

        CONTEXT:
        Subject: {request.subject}
        Grade: {request.gradeLevel}

        USER FEEDBACK / INSTRUCTIONS:
        "{request.feedback}"

        CURRENT DECK JSON:
        {current_deck_json}

        TASK:
        1. Apply the user's feedback to the deck.
        2. Keep the same structure (Title, Slides list).
        3. If slides need to be added/removed/edited, do so.
        4. Return the COMPLETE updated JSON.
        """

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=3000,
            temperature=0.7
        )
        
        # We need to re-process visuals IF the content changed significantly, 
        # but for simplicity/speed in this iteration, we will just return the text changes 
        # and let the frontend/backend handle visual re-generation if needed later.
        # However, to match response_model, we need to ensure structure is correct.

        # Re-construct slides
        updated_slides = []
        for s in result.get("slides", []):
             # basic validation/reconstruction to match schema
             updated_slides.append(Slide(
                 title=s.get("title", "Untitled"),
                 content=s.get("content", ""),
                 order=s.get("order", 0),
                 visualMetadata=None # Reset visuals on modify for now to be safe, or we could try to preserve
             ))

        return DeckGenerateResponse(
            title=result.get("title", request.currentDeck.get("title")),
            slides=updated_slides
        )

    except Exception as e:
        logger.error(f"Deck modification failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to modify deck: {str(e)}")


@router.post("/generate-deck", response_model=DeckGenerateResponse)
async def generate_deck(request: DeckGenerateRequest):
    """Generate a teaching deck using AI with smart visual routing and generation"""
    try:
        # Enhanced system message with instructional design expertise
        system_message = """You are an elite instructional designer and master teacher with expertise in creating compelling educational presentations. You understand learning science, cognitive load theory, and how to structure information for maximum retention.

Your presentations are known for:
- Clear narrative flow that builds understanding step-by-step
- Perfect balance between content depth and visual clarity
- Age-appropriate language and examples that resonate with students
- Engaging hooks and memorable takeaways
- Strategic use of questions, examples, and applications
- Content formatted for visual presentation (not essays)

You create slide content that teachers can directly use with minimal editing. Each slide is focused, visually presentable, and designed to facilitate discussion rather than being read verbatim.

Always respond with valid, well-structured JSON."""

        # Calculate recommended slide allocation
        intro_slides = 1
        conclusion_slides = 1
        content_slides = request.numSlides - 2
        
        prompt = f"""Design a comprehensive teaching presentation deck with exceptional pedagogical structure.

PRESENTATION SPECIFICATIONS:
- Topic: "{request.topic}"
- Subject: {request.subject}
- Grade Level: {request.gradeLevel}
- Total Slides: {request.numSlides} (including intro and conclusion)

INSTRUCTIONAL DESIGN FRAMEWORK:

1. NARRATIVE STRUCTURE:
   - Slide 1: Hook + Learning Objectives (What will students discover?)
   - Slides 2-{content_slides + 1}: Core content with logical progression
   - Slide {request.numSlides}: Summary + Call-to-Action/Reflection

2. COGNITIVE LOAD PRINCIPLES:
   - Each slide should focus on ONE main idea
   - Use 3-5 concise bullet points OR 2-3 short paragraphs per slide
   - Break complex concepts across multiple slides rather than cramming
   - Include transition phrases between concepts

3. CONTENT REQUIREMENTS PER SLIDE:

   **Introduction Slide (Slide 1):**
   - Compelling hook/question that sparks curiosity
   - 2-4 clear learning objectives starting with action verbs
   - Optional: Relevant real-world connection

   **Content Slides (Slides 2-{content_slides + 1}):**
   - Clear, specific title (not generic like "Main Concept")
   - 3-5 bullet points OR 2-3 short paragraphs
   - Each point should be presentation-ready (concise, not full sentences unless needed)
   - Include at least 2 slides with concrete examples or applications
   - Include at least 1 slide with a thought-provoking question or discussion prompt
   - Use analogies, metaphors, or real-world connections for abstract concepts
   - Progressive complexity: start simple, build to more sophisticated ideas

   **Conclusion Slide (Slide {request.numSlides}):**
   - 3-4 key takeaways (what students should remember)
   - Connection to bigger picture or real-world application
   - Reflection question or next steps

4. AGE-APPROPRIATE ADAPTATION FOR {request.gradeLevel}:
   - Vocabulary and sentence complexity suitable for this grade
   - Examples and references relevant to students' lives and interests
   - Appropriate cognitive expectations (concrete vs. abstract thinking)
   - Engagement strategies matching attention span and maturity

5. SUBJECT-SPECIFIC CONSIDERATIONS FOR {request.subject}:
   - Use discipline-appropriate terminology and frameworks
   - Include relevant examples from the field
   - Consider what visuals or diagrams might accompany content (mention in brackets if helpful)

6. ENGAGEMENT ELEMENTS (distribute across deck):
   - At least 1 thought-provoking question slide
   - At least 1 real-world application or example
   - At least 1 opportunity for student reflection or prediction
   - Use "you" language to directly address students

OUTPUT FORMAT (return as JSON):
{{
    "title": "Engaging, specific presentation title (not just the topic)",
    "slides": [
        {{
            "title": "Specific, Clear Slide Title",
            "content": "• Bullet point 1: Concise, presentation-ready text
• Bullet point 2: Use formatting like bold **terms** or [Visual: diagram suggestion]
• Bullet point 3: Each point is digestible and focused
• Bullet point 4: Include examples, not just definitions
• Optional 5th point if needed

OR for conceptual slides:

Opening paragraph that introduces the concept clearly.

Second paragraph that provides example or elaboration. Keep paragraphs short (2-4 sentences max).

[Optional note about visuals, activities, or discussion prompts]",
            "order": 1
        }},
        {{
            "title": "Next Slide Title",
            "content": "Content for slide 2...",
            "order": 2
        }}
    ]
}}

CRITICAL QUALITY STANDARDS:
- Each slide must be teachable in 2-4 minutes of class time
- Content should prompt discussion, not just be read aloud
- Use specific examples, not abstract generalities
- Maintain consistent depth appropriate to {request.gradeLevel}
- Ensure logical flow where each slide builds on previous ones
- Avoid information overload - less is more
- Write for slides, not for reading (visual-friendly format)
- Include exactly {request.numSlides} slides, properly numbered 1-{request.numSlides}

CONTENT STRUCTURE CHECKLIST:
✓ Slide 1: Engaging intro with clear objectives
✓ Early slides: Foundational concepts and definitions
✓ Middle slides: Development, examples, applications
✓ Later slides: Synthesis, complex applications
✓ Final slide: Memorable summary and reflection

Generate the complete {request.numSlides}-slide presentation deck now. Make it engaging, clear, and immediately usable for classroom teaching."""

        # Step 1: Generate slide text content
        logger.info(f"Generating deck for topic: {request.topic}, subject: {request.subject}")
        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=3000,
            temperature=0.7
        )

        # Validate slide count matches request
        if len(result["slides"]) != request.numSlides:
            logger.warning(f"Generated {len(result['slides'])} slides but {request.numSlides} were requested")

        # Step 2: Route slides to appropriate visual generators
        logger.info(f"Analyzing {len(result['slides'])} slides for visual routing...")
        
        # Prepare slides for batch routing
        slides_for_routing = [
            {"title": slide["title"], "content": slide["content"]}
            for slide in result["slides"]
        ]
        
        # Get visual routing results
        visual_routes = await batch_route_slides(
            slides=slides_for_routing,
            subject=request.subject,
            enable_paid_services=False  # Will enable in Phase 3
        )

        # Step 3: Generate actual visuals for routed slides
        logger.info(f"Generating visuals for slides...")
        visual_results = await batch_generate_visuals(
            slides=slides_for_routing,
            visual_routes=visual_routes,
            subject=request.subject
        )

        # Step 4: Combine everything - text content + visual metadata + generated visuals
        enriched_slides = []
        for slide_data, visual_route, visual_result in zip(result["slides"], visual_routes, visual_results):
            # Create visual metadata with generated visual data
            visual_metadata = None
            if visual_route.get('visualType') and visual_result.get('success'):
                # Merge routing info with generated visual
                visual_config = visual_route.get('visualConfig', {})
                visual_config['generatedData'] = visual_result.get('data', {})
                
                visual_metadata = VisualMetadata(
                    visualType=visual_route['visualType'],
                    visualConfig=visual_config,
                    confidence=visual_route.get('confidence'),
                    generatedBy=visual_route.get('generatedBy'),
                    reasoning=visual_route.get('reasoning')
                )
            
            slide = Slide(
                title=slide_data["title"],
                content=slide_data["content"],
                order=slide_data["order"],
                visualMetadata=visual_metadata
            )
            enriched_slides.append(slide)
        
        # Log statistics
        visuals_generated = sum(1 for r in visual_results if r.get('success'))
        logger.info(f"Deck generation complete: {len(enriched_slides)} slides, "
                   f"{visuals_generated} visuals generated successfully")

        return DeckGenerateResponse(
            title=result["title"],
            slides=enriched_slides
        )

    except Exception as e:
        logger.error(f"Deck generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate deck: {str(e)}")
