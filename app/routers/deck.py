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
        
        # Regenerate visuals for the modified deck
        logger.info(f"Regenerating visuals for modified deck with {len(result.get('slides', []))} slides")
        
        # Prepare slides for visual routing
        slides_for_routing = [
            {"title": slide["title"], "content": slide["content"]}
            for slide in result.get("slides", [])
        ]
        
        # Get visual routing results
        visual_routes = await batch_route_slides(
            slides=slides_for_routing,
            subject=request.subject,
            enable_paid_services=False
        )

        # Generate actual visuals
        visual_results = await batch_generate_visuals(
            slides=slides_for_routing,
            visual_routes=visual_routes,
            subject=request.subject
        )

        # Combine text content + visual metadata
        updated_slides = []
        for slide_data, visual_route, visual_result in zip(result.get("slides", []), visual_routes, visual_results):
            # Create visual metadata if visual was generated
            visual_metadata = None
            if visual_route.get('visualType') and visual_result.get('success'):
                visual_config = visual_route.get('visualConfig', {})
                visual_config['generatedData'] = visual_result.get('data', {})
                
                visual_metadata = VisualMetadata(
                    visualType=visual_route['visualType'],
                    visualConfig=visual_config,
                    confidence=visual_route.get('confidence'),
                    generatedBy=visual_route.get('generatedBy'),
                    reasoning=visual_route.get('reasoning')
                )
            
            updated_slides.append(Slide(
                title=slide_data.get("title", "Untitled"),
                content=slide_data.get("content", ""),
                order=slide_data.get("order", 0),
                visualMetadata=visual_metadata
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
    """Generate a teaching deck using AI with structured topic sequence"""
    try:
        # Get topics list - support both new format (topics array) and legacy (single topic)
        topics_list = request.topics if request.topics else [request.topic] if request.topic else []
        
        if not topics_list:
            raise HTTPException(status_code=400, detail="No topics provided")
        
        # Use structured format if requested or if we have multiple topics
        use_structured = request.structuredFormat or len(topics_list) > 0
        
        if use_structured:
            # NEW STRUCTURED FORMAT: 5 slides per topic + 1 summary
            system_message = """You are an expert educational content designer specializing in creating structured teaching decks.
            
Your decks follow a precise pedagogical structure for each topic:
1. Definition - Clear, concise definition of the concept
2. Details & Explanation - In-depth explanation with examples
3. Basic Question - Simple question to check understanding
4. Numerical/Hard Question - Challenging problem requiring application
5. Olympiad Question - Extremely difficult, competition-level problem

You create content that is:
- Age-appropriate for the specified grade level
- Accurate and aligned with curriculum standards
- Engaging and thought-provoking
- Properly formatted for presentation

Always respond with valid JSON."""

            topics_str = ", ".join(topics_list)
            num_topics = len(topics_list)
            total_slides = num_topics * 5 + 1  # 5 per topic + 1 summary
            
            prompt = f"""Generate a structured teaching deck for the following:

SPECIFICATIONS:
- Subject: {request.subject}
- Grade Level: {request.gradeLevel}
- Chapter: {request.chapter or 'General'}
- Topics: {topics_str}
- Number of Topics: {num_topics}
- Total Slides Required: {total_slides}

STRICT STRUCTURE (follow this EXACTLY for EACH topic):

For each topic, create exactly 5 slides in this order:

**Slide Type 1: DEFINITION**
- Title: "[Topic Name]: Definition"
- Content: Clear, textbook-quality definition. Include key terms in bold.
- Keep it concise: 2-3 sentences maximum.

**Slide Type 2: DETAILS & EXPLANATION**  
- Title: "Understanding [Topic Name]"
- Content: Detailed explanation with:
  • Key concepts and principles
  • Real-world examples
  • Important formulas (if applicable)
  • Visual descriptions [mention what diagrams would help]
- Use bullet points, 4-6 points.

**Slide Type 3: BASIC QUESTION (Easy)**
- Title: "[Topic Name]: Practice Question 1"
- Content: Simple question testing basic understanding.
  • State the question clearly
  • For MCQ, provide 4 options (A, B, C, D)
  • Include "Answer: [correct answer]" at the end
  • Brief explanation of why that's correct

📊 EASY DIFFICULTY BOUNDARIES:
- Solution steps: 1-3 steps MAXIMUM
- Completion time: Under 5 minutes
- Prior knowledge: None needed - question is self-contained
- Cognitive load: Single basic concept only

**Slide Type 4: NUMERICAL/HARD QUESTION (Medium)**
- Title: "[Topic Name]: Practice Question 2 (Challenging)"
- Content: Numerical problem or complex application question.
  • Multi-step problem requiring understanding
  • Show the problem setup clearly
  • Include "Solution:" with step-by-step working
  • Include "Answer: [final answer]"

📊 MEDIUM DIFFICULTY BOUNDARIES:
- Solution steps: 4-7 steps required
- Completion time: 10-20 minutes
- Prior knowledge: Assumes familiarity with basic domain concepts
- Cognitive load: Combines 2-3 related concepts

**Slide Type 5: OLYMPIAD QUESTION (Very Difficult/Hard)**
- Title: "[Topic Name]: Challenge Question (Olympiad Level)"
- Content: Extremely challenging problem.
  • Competition-style question (JEE/NEET/Olympiad level)
  • May combine multiple concepts across topics
  • Include "Approach:" with hints
  • Include "Solution:" with detailed working
  • Include "Answer: [final answer]"

📊 HARD DIFFICULTY BOUNDARIES:
- Solution steps: 8+ steps required
- Completion time: 30+ minutes
- Prior knowledge: Deep understanding required, synthesize multiple advanced concepts
- Cognitive load: Creative problem-solving, novel approaches needed
- Target: Only top 5% students should solve independently

**FINAL SLIDE: SUMMARY**
After all topics are covered, create ONE summary slide:
- Title: "Today's Learning Summary"
- Content: Bullet points covering:
  • Each topic we covered
  • Key formulas/concepts to remember
  • 2-3 key takeaways
- No new content, just consolidation.

TOPICS TO COVER (in order):
{chr(10).join([f"{i+1}. {topic}" for i, topic in enumerate(topics_list)])}

OUTPUT FORMAT:
{{
    "title": "{request.chapter or topics_list[0]}: Complete Teaching Deck",
    "slides": [
        {{"title": "Slide title", "content": "Slide content...", "order": 1}},
        {{"title": "Slide 2 title", "content": "Content...", "order": 2}},
        // ... continue for all {total_slides} slides
    ]
}}

IMPORTANT:
- Generate EXACTLY {total_slides} slides ({num_topics} topics × 5 slides + 1 summary)
- Follow the structure strictly: Definition → Details → Basic Q → Hard Q → Olympiad Q for EACH topic
- Questions MUST include answers and solutions
- Use proper mathematical notation where needed
- Make content grade-appropriate for Class {request.gradeLevel}

Generate the complete deck now."""

            logger.info(f"Generating structured deck for {num_topics} topics: {topics_str}")
            
        else:
            # Legacy format for backward compatibility (shouldn't normally reach here)
            system_message = """You are an educational content designer. Create engaging presentation content."""
            prompt = f"Create a simple deck about {request.topic} for {request.subject} grade {request.gradeLevel}"
            logger.info(f"Generating legacy deck for topic: {request.topic}")

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=4000,  # Increased for structured content
            temperature=0.7
        )

        # Validate slide count
        expected_slides = len(topics_list) * 5 + 1 if use_structured else request.numSlides
        if len(result["slides"]) != expected_slides:
            logger.warning(f"Generated {len(result['slides'])} slides but {expected_slides} were expected")

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
