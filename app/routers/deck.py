from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import DeckGenerateRequest, DeckGenerateResponse, Slide, VisualMetadata
from app.models.modify_schemas import DeckModifyRequest
from app.models.lesson_schema import LessonDeck, LessonMetadata, LearningStructure, LearningObjective, BloomLevel
from app.services.openai_service import generate_json_completion
from app.services.visual_routing import batch_route_slides
from app.services.visual_generator import batch_generate_visuals
from app.services.pptx_renderer import PPTXRenderer
import logging
import json
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

# Subject Classification Helper
def classify_subject(subject: str) -> str:
    """
    Classify a subject as either 'quantitative' or 'descriptive'.
    
    Quantitative subjects focus on numerical calculations and formulas.
    Descriptive subjects focus on concepts, analysis, and interpretation.
    """
    quantitative_keywords = [
        'math', 'physics', 'chemistry', 'economics', 'accounting', 
        'statistics', 'computer science', 'cs', 'calculus', 'algebra'
    ]
    
    subject_lower = subject.lower()
    
    # Check if any quantitative keyword is in the subject name
    is_quantitative = any(keyword in subject_lower for keyword in quantitative_keywords)
    
    return 'quantitative' if is_quantitative else 'descriptive'

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
        
        # DEFENSIVE: Ensure all topics are strings (handle any edge cases)
        topics_list = [str(topic) for topic in topics_list if topic]
        
        # Use structured format if requested or if we have multiple topics
        use_structured = request.structuredFormat or len(topics_list) > 0
        
        if use_structured:
            # Classify subject type
            subject_type = classify_subject(request.subject)
            logger.info(f"Subject '{request.subject}' classified as: {subject_type}")
            
            topics_str = ", ".join(topics_list)
            num_topics = len(topics_list)
            total_slides = num_topics * 5 + 1  # 5 per topic + 1 summary
            
            # === QUANTITATIVE SUBJECTS (Math, Physics, Chemistry) ===
            if subject_type == 'quantitative':
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
"""
            
            # === DESCRIPTIVE SUBJECTS (English, History, Geography, etc.) ===
            else:
                system_message = """You are an expert educational content designer specializing in creating structured teaching decks for descriptive subjects.

Your decks follow a precise pedagogical structure for each topic:
1. Definition/Key Term - Clear explanation of the concept or term
2. Explanation with Context - Detailed explanation with historical/literary context
3. Easy Question - Recall/identification question
4. Medium Question - Analysis/comparison question
5. Hard Question - Synthesis/evaluation question

You create content that is:
- Age-appropriate for the specified grade level
- Historically/contextually accurate
- Engaging and thought-provoking
- Properly formatted for presentation

Always respond with valid JSON."""

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

**Slide Type 1: DEFINITION/KEY TERM**
- Title: "[Topic Name]: Key Concept"
- Content: Clear definition or explanation of the key term.
  • Define the concept in 2-3 sentences
  • Provide historical/literary context if relevant
  • Mention significance or importance

**Slide Type 2: EXPLANATION WITH CONTEXT**
- Title: "Understanding [Topic Name]"
- Content: Detailed explanation with:
  • Background and historical/literary context
  • Key characteristics or features
  • Real-world examples or case studies
  • Connections to other related concepts
- Use bullet points, 4-6 points.

**Slide Type 3: EASY QUESTION (Recall/Identification)**
- Title: "[Topic Name]: Practice Question 1"
- Content: Question testing basic understanding and recall.
  • "Who was...", "What is...", "When did...", "Where did..."
  • For MCQ, provide 4 options (A, B, C, D)
  • Include "Answer: [correct answer]" at the end
  • Brief explanation

📊 EASY DIFFICULTY BOUNDARIES:
- Question type: Direct recall, identification, basic facts
- Completion time: Under 5 minutes
- Cognitive level: Remember, Identify

**Slide Type 4: MEDIUM QUESTION (Analysis/Comparison)**
- Title: "[Topic Name]: Practice Question 2 (Analytical)"
- Content: Question requiring analysis or comparison.
  • "Compare X and Y", "Explain the significance of...", "What were the causes of..."
  • "Differentiate between...", "Describe the characteristics of..."
  • Include "Answer:" with detailed explanation
  • Mention multiple aspects or perspectives

📊 MEDIUM DIFFICULTY BOUNDARIES:
- Question type: Compare, Contrast, Explain, Analyze
- Completion time: 10-15 minutes
- Cognitive level: Understand, Analyze, Compare

**Slide Type 5: HARD QUESTION (Synthesis/Evaluation)**
- Title: "[Topic Name]: Challenge Question (Critical Thinking)"
- Content: Question requiring synthesis and evaluation.
  • "How does X relate to Y?", "Analyze the impact of...", "Evaluate the role of..."
  • "To what extent...", "Justify...", "Critically assess..."
  • Include "Approach:" with thinking framework
  • Include "Answer:" with comprehensive analysis
  • Discuss multiple viewpoints or interpretations

📊 HARD DIFFICULTY BOUNDARIES:
- Question type: Evaluate, Synthesize, Justify, Critically analyze
- Completion time: 20-30 minutes
- Cognitive level: Synthesize, Evaluate, Create connections
- Target: Requires deep understanding and critical thinking

**FINAL SLIDE: SUMMARY**
After all topics are covered, create ONE summary slide:
- Title: "Today's Learning Summary"
- Content: Bullet points covering:
  • Each topic we covered
  • Key concepts/events/ideas to remember
  • 2-3 key takeaways or insights
- No new content, just consolidation.


TOPICS TO COVER (in order):
"""
            
            # Construct topics list formatting (common for both)
            topics_formatted = "\n".join([f"{i+1}. {topic}" for i, topic in enumerate(topics_list)])
            prompt += topics_formatted + "\n"
            
            prompt += f"""
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
- Follow the structure strictly: Definition → Explanation → Easy Q → Medium Q → Hard Q for EACH topic
- Questions MUST include answers and detailed explanations
- Make content grade-appropriate for Class {request.gradeLevel}

Generate the complete deck now."""

            logger.info(f"Generating structured {subject_type} deck for {num_topics} topics: {topics_str}")
            
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
        # Prepare slides for batch routing
        slides_for_routing = []
        for slide in result["slides"]:
            content = slide.get("content", "")
            # Sanitize content if it's not a string (handle lists from LLM)
            if isinstance(content, list):
                content = "\n".join([str(item) for item in content])
            elif isinstance(content, dict):
                content = json.dumps(content)
            elif not isinstance(content, str):
                content = str(content)
                
            slides_for_routing.append({
                "title": slide.get("title", ""),
                "content": content
            })
        
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


@router.post("/generate-deck-pptx")
async def generate_deck_pptx(request: DeckGenerateRequest):
    """
    Complete pipeline: Outline -> Content (parallel) -> PPTX
    This replaces the old logic with the new Bloom's-aligned agents.
    """
    try:
        logger.info(f"[PPTX EXPORT] Starting for topic: {request.topic or request.topics}")
        
        # Step 1: Generate outline
        from app.agents.deck_agents import OutlinerAgent, ContentAgent
        outline = await OutlinerAgent.create_outline(
            topic=request.topic or ", ".join(request.topics),
            subject=request.subject,
            grade_level=request.gradeLevel
        )
        
        # Step 2: Generate content in parallel
        slides_data = await ContentAgent.generate_all_slides_parallel(
            outline=outline,
            subject=request.subject,
            grade_level=request.gradeLevel
        )
        
        # Step 3: Create LessonDeck
        from app.models.lesson_schema import LessonDeck, LessonMetadata, LearningStructure, LearningObjective, Slide, DifferentiationLevel
        
        slides = [Slide(**s) for s in slides_data]
        
        lesson_deck = LessonDeck(
            meta=LessonMetadata(
                topic=request.topic or ", ".join(request.topics),
                subject=request.subject,
                grade=request.gradeLevel,
                theme=request.theme
            ),
            structure=LearningStructure(
                learning_objectives=[
                    LearningObjective(objective=s.objective, bloom_level=s.bloom_level)
                    for s in slides[:3] if s.objective
                ],
                vocabulary=[],
                prerequisites=[],
                bloom_progression=[s.bloom_level for s in slides]
            ),
            slides=slides
        )
        
        # Step 3.5: Differentiate if requested
        if request.level and request.level != DifferentiationLevel.CORE:
            logger.info(f"[PPTX EXPORT] Differentiating to level: {request.level}")
            from app.services.differentiation import DifferentiationService
            diff_service = DifferentiationService()
            lesson_deck = await diff_service.generate_differentiated_deck(
                core_deck=lesson_deck,
                target_level=request.level
            )
        
        # Step 4: Render to PPTX
        renderer = PPTXRenderer(theme=request.theme)
        pptx_file = await renderer.render_lesson_deck(lesson_deck)
        
        filename = f"{request.topic or 'lesson'}_{request.level or 'core'}.pptx".replace(' ', '_')
        return StreamingResponse(
            pptx_file,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"PPTX export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PPTX: {str(e)}")


@router.post("/generate-complete")
async def generate_complete_deck(request: DeckGenerateRequest):
    """
    Complete pipeline: Outline → Content (parallel) → PPTX
    
    This endpoint combines all stages:
    1. Generate curriculum-aligned outline with Bloom's progression
    2. Generate slide content in parallel (with speaker notes + image queries)
    3. Render to PPTX with embedded images
    4. Return downloadable file
    
    Performance: ~30-45 seconds for 10-slide deck
    
    Returns:
        StreamingResponse with .pptx file
    """
    try:
        logger.info(f"[COMPLETE PIPELINE] Starting for topic: {request.topic or request.topics}")
        
        # Step 1: Generate curriculum-aligned outline with Bloom's progression
        logger.info("[Step 1/4] Generating outline...")
        from app.agents.deck_agents import OutlinerAgent, ContentAgent
        
        outline = await OutlinerAgent.create_outline(
            topic=request.topic or ", ".join(request.topics),
            subject=request.subject,
            grade_level=request.gradeLevel
        )
        
        logger.info(f"✓ Outline created: {len(outline)} slides")
        
        # Step 2: Generate all slide content in parallel
        logger.info("[Step 2/4] Generating slide content (parallel)...")
        slides = await ContentAgent.generate_all_slides_parallel(
            outline=outline,
            subject=request.subject,
            grade_level=request.gradeLevel
        )
        
        logger.info(f"✓ Content generated for {len(slides)} slides")
        
        # Step 3: Create LessonDeck structure
        logger.info("[Step 3/4] Creating LessonDeck...")
        from app.models.lesson_schema import LessonDeck, LessonMetadata, LearningStructure, LearningObjective
        
        # Extract learning objectives from slides
        learning_objectives = []
        for slide in slides[:3]:  # Take first 3 slides as main objectives
            if slide.get('objective'):
                learning_objectives.append(
                    LearningObjective(
                        objective=slide['objective'],
                        bloom_level=slide.get('bloom_level', 'UNDERSTAND')
                    )
                )
        
        lesson_deck = LessonDeck(
            meta=LessonMetadata(
                topic=request.topic or ", ".join(request.topics),
                grade=request.gradeLevel,
                subject=request.subject,
                standards=[],  # Will be populated from RAG context
                theme=request.theme or "default",
                pedagogical_model="I_DO_WE_DO_YOU_DO"
            ),
            structure=LearningStructure(
                learning_objectives=learning_objectives,
                vocabulary=[],
                prerequisites=[],
                bloom_progression=[s.get('bloom_level', 'UNDERSTAND') for s in slides]
            ),
            slides=slides
        )
        
        return lesson_deck
        
    except Exception as e:
        logger.error(f"[COMPLETE PIPELINE] ❌ Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")


@router.post("/generate-all-levels")
async def generate_all_differentiation_levels(request: DeckGenerateRequest):
    """
    Generate all three differentiation levels (Support, Core, Extension) in parallel.
    
    This endpoint:
    1. Generates the CORE deck first (complete pipeline)
    2. Generates SUPPORT and EXTENSION versions in parallel from core
    3. Returns all three versions as PPTX files or JSON
    
    Performance: ~50-60 seconds for all 3 versions
    
    Returns:
        {
            "support": {"deck": LessonDeck, "slide_count": int},
            "core": {"deck": LessonDeck, "slide_count": int},
            "extension": {"deck": LessonDeck, "slide_count": int}
        }
    """
    try:
        logger.info(f"[DIFFERENTIATION] Generating all levels for: {request.topic or request.topics}")
        
        # Step 1: Generate CORE deck using complete pipeline
        logger.info("[Step 1/3] Generating CORE deck...")
        from app.agents.deck_agents import OutlinerAgent, ContentAgent
        from app.services.differentiation import DifferentiationService, DifferentiationLevel
        
        # Generate outline
        outline = await OutlinerAgent.create_outline(
            topic=request.topic or ", ".join(request.topics),
            subject=request.subject,
            grade_level=request.gradeLevel
        )
        
        # Generate slides in parallel
        slides = await ContentAgent.generate_all_slides_parallel(
            outline=outline,
            subject=request.subject,
            grade_level=request.gradeLevel
        )
        
        # Create core LessonDeck
        from app.models.lesson_schema import LessonDeck, LessonMetadata, LearningStructure, LearningObjective
        
        learning_objectives = []
        for slide in slides[:3]:
            if slide.get('objective'):
                learning_objectives.append(
                    LearningObjective(
                        objective=slide['objective'],
                        bloom_level=slide.get('bloom_level', 'UNDERSTAND')
                    )
                )
        
        core_deck = LessonDeck(
            meta=LessonMetadata(
                topic=request.topic or ", ".join(request.topics),
                grade=request.gradeLevel,
                subject=request.subject,
                standards=[],
                theme=request.theme or "default",
                pedagogical_model="I_DO_WE_DO_YOU_DO"
            ),
            structure=LearningStructure(
                learning_objectives=learning_objectives,
                vocabulary=[],
                prerequisites=[],
                bloom_progression=[s.get('bloom_level', 'UNDERSTAND') for s in slides]
            ),
            slides=slides
        )
        
        logger.info(f"✓ CORE deck created: {len(slides)} slides")
        
        # Step 2: Generate SUPPORT and EXTENSION in parallel
        logger.info("[Step 2/3] Generating SUPPORT and EXTENSION versions (parallel)...")
        
        diff_service = DifferentiationService()
        
        support_task = diff_service.generate_differentiated_deck(
            core_deck=core_deck,
            target_level=DifferentiationLevel.SUPPORT
        )
        
        extension_task = diff_service.generate_differentiated_deck(
            core_deck=core_deck,
            target_level=DifferentiationLevel.EXTENSION
        )
        
        support_deck, extension_deck = await asyncio.gather(support_task, extension_task)
        
        logger.info(f"✓ SUPPORT deck: {len(support_deck.slides)} slides")
        logger.info(f"✓ EXTENSION deck: {len(extension_deck.slides)} slides")
        
        # Step 3: Return all three versions as JSON
        logger.info("[Step 3/3] Returning all versions...")
        
        result = {
            "support": support_deck.dict(),
            "core": core_deck.dict(),
            "extension": extension_deck.dict()
        }
        
        logger.info("[DIFFERENTIATION] ✅ All levels generated successfully")
        
        return result
        
    except Exception as e:
        logger.error(f"[DIFFERENTIATION] ❌ Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Differentiation failed: {str(e)}")


@router.post("/generate-level/{level}")
async def generate_specific_level(
    level: str,
    request: DeckGenerateRequest
):
    """
    Generate a deck at a specific differentiation level.
    
    Args:
        level: "support", "core", or "extension"
        request: Deck generation request
        
    Returns:
        LessonDeck at the specified level
    """
    try:
        # Normalize level input
        level_map = {
            "support": "SUPPORT",
            "core": "CORE",
            "extension": "EXTENSION"
        }
        
        target_level_str = level_map.get(level.lower())
        if not target_level_str:
            raise HTTPException(status_code=400, detail=f"Invalid level: {level}. Must be support, core, or extension")
        
        from app.services.differentiation import DifferentiationLevel
        target_level = DifferentiationLevel(target_level_str)
        
        logger.info(f"[LEVEL GENERATION] Generating {target_level} deck...")
        
        # If CORE, use standard pipeline
        if target_level == DifferentiationLevel.CORE:
            return await generate_complete_deck(request)
        
        # Otherwise, generate core first then differentiate
        from app.agents.deck_agents import OutlinerAgent, ContentAgent
        from app.services.differentiation import DifferentiationService
        from app.models.lesson_schema import LessonDeck, LessonMetadata, LearningStructure, LearningObjective
        
        # Generate core deck
        outline = await OutlinerAgent.create_outline(
            topic=request.topic or ", ".join(request.topics),
            subject=request.subject,
            grade_level=request.gradeLevel
        )
        
        slides = await ContentAgent.generate_all_slides_parallel(
            outline=outline,
            subject=request.subject,
            grade_level=request.gradeLevel
        )
        
        learning_objectives = []
        for slide in slides[:3]:
            if slide.get('objective'):
                learning_objectives.append(
                    LearningObjective(
                        objective=slide['objective'],
                        bloom_level=slide.get('bloom_level', 'UNDERSTAND')
                    )
                )
        
        core_deck = LessonDeck(
            meta=LessonMetadata(
                topic=request.topic or ", ".join(request.topics),
                grade=request.gradeLevel,
                subject=request.subject,
                standards=[],
                theme=request.theme or "default",
                pedagogical_model="I_DO_WE_DO_YOU_DO"
            ),
            structure=LearningStructure(
                learning_objectives=learning_objectives,
                vocabulary=[],
                prerequisites=[],
                bloom_progression=[s.get('bloom_level', 'UNDERSTAND') for s in slides]
            ),
            slides=slides
        )
        
        # Differentiate
        diff_service = DifferentiationService()
        differentiated_deck = await diff_service.generate_differentiated_deck(
            core_deck=core_deck,
            target_level=target_level
        )
        
        logger.info(f"✓ {target_level} deck generated with {len(differentiated_deck.slides)} slides")
        
        return differentiated_deck.dict()
        
    except Exception as e:
        logger.error(f"[LEVEL GENERATION] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Level generation failed: {str(e)}")
