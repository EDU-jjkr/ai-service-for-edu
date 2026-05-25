from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import DeckGenerateRequest, DeckGenerateResponse, Slide, VisualMetadata, PPTXRenderRequest
from app.models.modify_schemas import DeckModifyRequest
from app.models.lesson_schema import LessonDeck, LessonMetadata, LearningStructure, LearningObjective, BloomLevel, SlideType, PedagogicalRole, ContentMode, DensityLevel, ImportanceLevel, VisualIntent, EditingHints, PracticeMetadata, ContentBlock
from app.services.openai_service import generate_json_completion
from app.services.deck_schema_builder import build_structured_slides_from_plan, expand_structured_slides_to_outline
from app.services.lesson_narrative_planner import build_lesson_narrative_plan
from app.services.pedagogy_flows import select_pedagogy_flow
from app.services.visual_routing import batch_route_slides
from app.services.visual_generator import batch_generate_visuals
from app.services.pptx_renderer import PPTXRenderer
from app.services.slide_quality import apply_quality_guards_to_lesson
from app.services.prompt_stack import build_lesson_planner_prompt, build_slide_author_prompt
import logging
import json
import asyncio
from pydantic import BaseModel
from typing import Any, Optional

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


def _enum_value(enum_cls, value, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls[value.upper()]
        except KeyError:
            try:
                return enum_cls(value.upper())
            except ValueError:
                return default
    return default


def _build_response(lesson_deck: LessonDeck, title: str | None = None) -> DeckGenerateResponse:
    lesson_deck = apply_quality_guards_to_lesson(lesson_deck)
    response_title = title or lesson_deck.meta.topic
    return DeckGenerateResponse(
        lesson=lesson_deck,
        title=response_title,
        meta=lesson_deck.meta.model_dump(mode="json"),
        structure=lesson_deck.structure.model_dump(mode="json"),
        slides=lesson_deck.slides,
    )


def _serialize_lesson_deck_payload(lesson_deck: LessonDeck, title: str | None = None) -> dict[str, Any]:
    response = _build_response(lesson_deck, title=title)
    return {
        "title": response.title,
        "meta": response.meta,
        "structure": response.structure,
        "slides": [slide.model_dump(mode="json") for slide in response.slides],
    }


def _lesson_from_payload(
    slides_data,
    topic: str,
    subject: str,
    grade_level: str,
    theme: str = "default",
    meta: dict | None = None,
    structure: dict | None = None,
    fallback_slides: list[Slide] | None = None,
) -> LessonDeck:
    slide_objects = []

    for i, slide in enumerate(slides_data):
        fallback_slide = fallback_slides[i] if fallback_slides and i < len(fallback_slides) else None
        slide_obj = Slide(
            title=slide.get("title") or (fallback_slide.title if fallback_slide else f"Slide {i+1}"),
            content=slide.get("content") or (fallback_slide.content if fallback_slide else ""),
            order=slide.get("order", i + 1),
            slideType=_enum_value(
                SlideType,
                slide.get("slideType") or slide.get("type") or (fallback_slide.slideType.value if fallback_slide else None),
                fallback_slide.slideType if fallback_slide else SlideType.CONCEPT,
            ),
            bloom_level=_enum_value(
                BloomLevel,
                slide.get("bloom_level") or (fallback_slide.bloom_level.value if fallback_slide else None),
                fallback_slide.bloom_level if fallback_slide else BloomLevel.UNDERSTAND,
            ),
            objective=slide.get("objective") or (fallback_slide.objective if fallback_slide else None),
            speakerNotes=slide.get("speakerNotes") or slide.get("speaker_notes") or (fallback_slide.speakerNotes if fallback_slide else None),
            imageQuery=slide.get("imageQuery") or slide.get("image_query") or (fallback_slide.imageQuery if fallback_slide else None),
            visualMetadata=(
                VisualMetadata(**slide["visualMetadata"])
                if slide.get("visualMetadata")
                else (fallback_slide.visualMetadata if fallback_slide else None)
            ),
            clusterId=slide.get("clusterId") or (fallback_slide.clusterId if fallback_slide else None),
            pedagogicalRole=_enum_value(
                PedagogicalRole,
                slide.get("pedagogicalRole") or (fallback_slide.pedagogicalRole.value if fallback_slide and fallback_slide.pedagogicalRole else None),
                fallback_slide.pedagogicalRole if fallback_slide else None,
            ),
            instructionalGoal=slide.get("instructionalGoal") or (fallback_slide.instructionalGoal if fallback_slide else None),
            contentMode=_enum_value(
                ContentMode,
                slide.get("contentMode") or (fallback_slide.contentMode.value if fallback_slide and fallback_slide.contentMode else None),
                fallback_slide.contentMode if fallback_slide else None,
            ),
            contentBlocks=[
                block if isinstance(block, ContentBlock) else ContentBlock(**block)
                for block in (
                    slide.get("contentBlocks")
                    or ([block.model_dump(mode="json") for block in fallback_slide.contentBlocks] if fallback_slide and fallback_slide.contentBlocks else [])
                )
            ],
            layoutCandidates=slide.get("layoutCandidates") or (fallback_slide.layoutCandidates if fallback_slide else []),
            density=_enum_value(
                DensityLevel,
                slide.get("density") or (fallback_slide.density.value if fallback_slide and fallback_slide.density else None),
                fallback_slide.density if fallback_slide else None,
            ),
            importance=_enum_value(
                ImportanceLevel,
                slide.get("importance") or (fallback_slide.importance.value if fallback_slide and fallback_slide.importance else None),
                fallback_slide.importance if fallback_slide else None,
            ),
            visualIntent=(
                VisualIntent(**slide["visualIntent"])
                if slide.get("visualIntent")
                else (fallback_slide.visualIntent if fallback_slide else None)
            ),
            editingHints=(
                EditingHints(**slide["editingHints"])
                if slide.get("editingHints")
                else (fallback_slide.editingHints if fallback_slide else None)
            ),
            practiceMetadata=(
                PracticeMetadata(**slide["practiceMetadata"])
                if slide.get("practiceMetadata")
                else (fallback_slide.practiceMetadata if fallback_slide else None)
            ),
        )
        slide_objects.append(slide_obj)

    lesson_meta = LessonMetadata(
        topic=meta.get("topic", topic) if meta else topic,
        grade=meta.get("grade", grade_level) if meta else grade_level,
        subject=meta.get("subject", subject) if meta else subject,
        standards=meta.get("standards", []) if meta else [],
        theme=meta.get("theme", theme) if meta else theme,
        pedagogical_model=meta.get("pedagogical_model", "I_DO_WE_DO_YOU_DO") if meta else "I_DO_WE_DO_YOU_DO",
        pedagogical_flow=meta.get("pedagogical_flow", "default_classroom") if meta else "default_classroom",
    )
    lesson_structure = LearningStructure(
        learning_objectives=[
            LearningObjective(
                objective=obj.get("objective", ""),
                bloom_level=_enum_value(BloomLevel, obj.get("bloom_level"), BloomLevel.UNDERSTAND),
            )
            for obj in (structure.get("learning_objectives", []) if structure else [])
            if obj.get("objective")
        ],
        vocabulary=structure.get("vocabulary", []) if structure else [],
        prerequisites=structure.get("prerequisites", []) if structure else [],
        bloom_progression=[
            _enum_value(BloomLevel, level, BloomLevel.UNDERSTAND)
            for level in (structure.get("bloom_progression", []) if structure else [])
        ] if structure else [slide.bloom_level for slide in slide_objects],
    )

    if not lesson_structure.learning_objectives:
        lesson_structure.learning_objectives = [
            LearningObjective(objective=slide.objective or slide.title, bloom_level=slide.bloom_level)
            for slide in slide_objects[:3]
        ]

    return LessonDeck(
        meta=lesson_meta,
        structure=lesson_structure,
        slides=slide_objects,
    )


class DeckRegenerateClusterRequest(BaseModel):
    deckId: str
    clusterId: str
    pedagogicalRole: str
    subject: str
    gradeLevel: str
    currentDeck: dict[str, Any]
    theme: Optional[str] = None


def _slide_match_key(slide: dict[str, Any]) -> tuple[Any, ...]:
    return (
        slide.get("id"),
        (slide.get("title") or "").strip().lower(),
        (slide.get("content") or "").strip().lower(),
    )


def _find_fallback_slide(
    *,
    slide_data: dict[str, Any],
    index: int,
    current_lesson_slides: list[dict[str, Any]],
) -> dict[str, Any]:
    slide_id = slide_data.get("id")
    if slide_id:
        for existing in current_lesson_slides:
            if existing.get("id") == slide_id:
                return existing

    target_title = (slide_data.get("title") or "").strip().lower()
    if target_title:
        for existing in current_lesson_slides:
            if (existing.get("title") or "").strip().lower() == target_title:
                return existing

    slide_key = _slide_match_key(slide_data)
    if any(slide_key[1:]):
        for existing in current_lesson_slides:
            if _slide_match_key(existing)[1:] == slide_key[1:]:
                return existing

    if index < len(current_lesson_slides):
        return current_lesson_slides[index]

    return {}


async def _build_modified_deck_response(
    *,
    current_deck: dict[str, Any],
    feedback: str,
    subject: str,
    grade_level: str,
    theme: Optional[str] = None,
) -> DeckGenerateResponse:
    current_deck_json = json.dumps(current_deck, indent=2)

    system_message = """You are an expert instructional designer revising a structured presentation deck.
    Apply the requested change while preserving the valid lesson-deck schema and existing structured metadata whenever possible."""

    prompt = f"""REVISE THIS DECK.

    CONTEXT:
    Subject: {subject}
    Grade: {grade_level}

    USER FEEDBACK / INSTRUCTIONS:
    "{feedback}"

    CURRENT DECK JSON:
    {current_deck_json}

    TASK:
    1. Apply the user's feedback to the deck.
    2. Preserve the complete structured lesson-deck shape with lesson/meta/structure/slides semantics.
    3. Keep structured slide metadata fields such as clusterId, pedagogicalRole, instructionalGoal, contentMode, contentBlocks, layoutCandidates, visualIntent, editingHints, and practiceMetadata unless the requested change requires a targeted update.
    4. Return the COMPLETE updated JSON.
    """

    result = await generate_json_completion(
        prompt=prompt,
        system_message=system_message,
        max_tokens=3000,
        temperature=0.7
    )

    slides_for_routing = [
        {"title": slide["title"], "content": slide["content"]}
        for slide in result.get("slides", [])
    ]

    visual_routes = await batch_route_slides(
        slides=slides_for_routing,
        subject=subject,
        enable_paid_services=False
    )

    visual_results = await batch_generate_visuals(
        slides=slides_for_routing,
        visual_routes=visual_routes,
        subject=subject
    )

    fallback_slides = []
    current_lesson = current_deck.get("lesson", {})
    current_lesson_slides = current_lesson.get("slides", [])

    for index, (slide_data, visual_route, visual_result) in enumerate(zip(result.get("slides", []), visual_routes, visual_results)):
        fallback_slide_data = _find_fallback_slide(
            slide_data=slide_data,
            index=index,
            current_lesson_slides=current_lesson_slides,
        )
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
        elif fallback_slide_data.get("visualMetadata"):
            visual_metadata = fallback_slide_data.get("visualMetadata")

        fallback_slides.append(Slide(
            id=slide_data.get("id") or fallback_slide_data.get("id"),
            title=slide_data.get("title", fallback_slide_data.get("title", "Untitled")),
            content=slide_data.get("content", fallback_slide_data.get("content", "")),
            order=slide_data.get("order", index + 1),
            slideType=_enum_value(SlideType, slide_data.get("slideType") or fallback_slide_data.get("slideType"), SlideType.CONCEPT),
            bloom_level=_enum_value(BloomLevel, slide_data.get("bloom_level") or fallback_slide_data.get("bloom_level"), BloomLevel.UNDERSTAND),
            objective=slide_data.get("objective") or fallback_slide_data.get("objective"),
            speakerNotes=slide_data.get("speakerNotes") or fallback_slide_data.get("speakerNotes"),
            imageQuery=slide_data.get("imageQuery") or fallback_slide_data.get("imageQuery"),
            visualMetadata=visual_metadata,
            clusterId=slide_data.get("clusterId") or fallback_slide_data.get("clusterId"),
            pedagogicalRole=_enum_value(PedagogicalRole, slide_data.get("pedagogicalRole") or fallback_slide_data.get("pedagogicalRole"), None),
            instructionalGoal=slide_data.get("instructionalGoal") or fallback_slide_data.get("instructionalGoal"),
            contentMode=_enum_value(ContentMode, slide_data.get("contentMode") or fallback_slide_data.get("contentMode"), None),
            contentBlocks=[ContentBlock(**block) for block in slide_data.get("contentBlocks", fallback_slide_data.get("contentBlocks", []))],
            layoutCandidates=slide_data.get("layoutCandidates") or fallback_slide_data.get("layoutCandidates", []),
            density=_enum_value(DensityLevel, slide_data.get("density") or fallback_slide_data.get("density"), None),
            importance=_enum_value(ImportanceLevel, slide_data.get("importance") or fallback_slide_data.get("importance"), None),
            visualIntent=VisualIntent(**slide_data["visualIntent"]) if slide_data.get("visualIntent") else (VisualIntent(**fallback_slide_data["visualIntent"]) if fallback_slide_data.get("visualIntent") else None),
            editingHints=EditingHints(**slide_data["editingHints"]) if slide_data.get("editingHints") else (EditingHints(**fallback_slide_data["editingHints"]) if fallback_slide_data.get("editingHints") else None),
            practiceMetadata=PracticeMetadata(**slide_data["practiceMetadata"]) if slide_data.get("practiceMetadata") else (PracticeMetadata(**fallback_slide_data["practiceMetadata"]) if fallback_slide_data.get("practiceMetadata") else None),
        ))

    lesson_deck = _lesson_from_payload(
        slides_data=result.get("slides", []),
        topic=(result.get("lesson", {}) or {}).get("meta", {}).get("topic") or result.get("title") or current_deck.get("title") or "Modified Deck",
        subject=subject,
        grade_level=grade_level,
        theme=theme or (current_lesson.get("meta", {}) or {}).get("theme", "default"),
        meta=result.get("meta") or current_lesson.get("meta"),
        structure=result.get("structure") or current_lesson.get("structure"),
        fallback_slides=fallback_slides,
    )
    return _build_response(lesson_deck, title=result.get("title", current_deck.get("title")))


def _build_structured_slide_shell(request: DeckGenerateRequest) -> list[Slide]:
    topics = request.topics if request.topics else [request.topic] if request.topic else []
    topic = topics if len(topics) > 1 else (topics[0] if topics else "")
    plan = build_lesson_narrative_plan(
        topic=topic,
        subject=request.subject,
        grade_level=request.gradeLevel,
        chapter=request.chapter,
        additional_instructions=request.additionalInstructions,
        pedagogy_flow=request.pedagogyFlow,
    )
    return build_structured_slides_from_plan(
        plan=plan,
        subject=request.subject,
        grade_level=request.gradeLevel,
    )


def _merge_generated_content_into_structured_slides(
    structured_slides: list[Slide],
    generated_slide_payloads: list[dict],
) -> list[Slide]:
    merged_slides: list[Slide] = []

    for index, structured_slide in enumerate(structured_slides):
        generated = generated_slide_payloads[index] if index < len(generated_slide_payloads) else {}
        slide = structured_slide.model_copy(deep=True)
        slide.order = index + 1
        slide.title = generated.get("title") or slide.title
        slide.content = generated.get("content") or slide.content
        slide.speakerNotes = generated.get("speakerNotes") or slide.speakerNotes
        slide.imageQuery = generated.get("imageQuery") or slide.imageQuery
        slide.objective = generated.get("objective") or slide.objective
        merged_slides.append(slide)

    return merged_slides


async def _generate_planned_lesson_deck(request: DeckGenerateRequest) -> LessonDeck:
    from app.agents.deck_agents import OutlinerAgent, ContentAgent

    topic = request.topic or ", ".join(request.topics)
    pedagogy_flow = select_pedagogy_flow(
        subject=request.subject,
        additional_instructions=request.additionalInstructions,
        requested_flow=request.pedagogyFlow,
    ).flow_id
    planner_prompt = build_lesson_planner_prompt(
        topic=topic,
        subject=request.subject,
        grade_level=request.gradeLevel,
        chapter=request.chapter,
        pedagogy_flow=pedagogy_flow,
        additional_instructions=request.additionalInstructions,
    )
    logger.debug("Built lesson planner prompt stack for topic '%s'", topic)

    outline = await OutlinerAgent.create_outline(
        topic=topic,
        subject=request.subject,
        grade_level=request.gradeLevel,
        prompt_bundle=planner_prompt,
    )

    structured_slides = _build_structured_slide_shell(request)
    structured_slides = expand_structured_slides_to_outline(structured_slides, outline)
    generation_outline = ContentAgent.build_generation_outline(
        structured_slides=structured_slides,
        outline=outline,
    )
    generation_outline = [
        {
            **slide_outline,
            "prompt_stack": build_slide_author_prompt(
                topic=topic,
                subject=request.subject,
                grade_level=request.gradeLevel,
                pedagogical_role=(
                    structured_slides[index].pedagogicalRole.value
                    if index < len(structured_slides) and structured_slides[index].pedagogicalRole
                    else "explain_core"
                ),
                instructional_goal=(
                    structured_slides[index].instructionalGoal
                    if index < len(structured_slides) and structured_slides[index].instructionalGoal
                    else slide_outline.get("objective") or slide_outline.get("title") or topic
                ),
            ),
        }
        for index, slide_outline in enumerate(generation_outline)
    ]

    generated_slide_payloads = await ContentAgent.generate_all_slides_parallel(
        outline=generation_outline,
        subject=request.subject,
        grade_level=request.gradeLevel,
    )

    slide_objects = _merge_generated_content_into_structured_slides(
        structured_slides=structured_slides,
        generated_slide_payloads=generated_slide_payloads,
    )

    slides_for_visuals = [
        {"title": slide.title, "content": slide.content}
        for slide in slide_objects
    ]
    visual_routes = await batch_route_slides(
        slides=slides_for_visuals,
        subject=request.subject,
        enable_paid_services=False,
    )
    visual_results = await batch_generate_visuals(
        slides=slides_for_visuals,
        visual_routes=visual_routes,
        subject=request.subject,
    )

    for slide_obj, visual_route, visual_result in zip(slide_objects, visual_routes, visual_results):
        if not visual_route.get("visualType") or not visual_result.get("success"):
            continue

        visual_config = dict(visual_route.get("visualConfig") or {})
        visual_config["generatedData"] = visual_result.get("data", {})
        slide_obj.visualMetadata = VisualMetadata(
            visualType=visual_route.get("visualType"),
            visualConfig=visual_config,
            confidence=visual_route.get("confidence"),
            generatedBy=visual_route.get("generatedBy"),
            reasoning=visual_route.get("reasoning"),
        )

    learning_objectives = [
        LearningObjective(
            objective=slide.objective or slide.title,
            bloom_level=slide.bloom_level,
        )
        for slide in slide_objects[:3]
    ]

    return LessonDeck(
        meta=LessonMetadata(
            topic=topic,
            grade=request.gradeLevel,
            subject=request.subject,
            standards=[],
            theme=request.theme or "default",
            pedagogical_model="I_DO_WE_DO_YOU_DO",
            pedagogical_flow=pedagogy_flow,
        ),
        structure=LearningStructure(
            learning_objectives=learning_objectives,
            vocabulary=[],
            prerequisites=[],
            bloom_progression=[slide.bloom_level for slide in slide_objects],
        ),
        slides=slide_objects,
    )


async def _generate_legacy_lesson_deck(
    request: DeckGenerateRequest,
    topics_list: list[str],
) -> LessonDeck:
    topic = request.topic or ", ".join(topics_list)
    result = await generate_json_completion(
        prompt=f"Create a simple deck about {topic} for {request.subject} grade {request.gradeLevel}",
        system_message="You are an educational content designer. Create engaging presentation content.",
        max_tokens=4000,
        temperature=0.7,
    )

    slides_for_routing = []
    for slide in result.get("slides", []):
        content = slide.get("content", "")
        if isinstance(content, list):
            content = "\n".join(str(item) for item in content)
        elif isinstance(content, dict):
            content = json.dumps(content)
        elif not isinstance(content, str):
            content = str(content)

        slides_for_routing.append(
            {
                "title": slide.get("title", ""),
                "content": content,
            }
        )

    visual_routes = await batch_route_slides(
        slides=slides_for_routing,
        subject=request.subject,
        enable_paid_services=False,
    )
    visual_results = await batch_generate_visuals(
        slides=slides_for_routing,
        visual_routes=visual_routes,
        subject=request.subject,
    )

    fallback_slides = []
    for slide_data, visual_route, visual_result in zip(result.get("slides", []), visual_routes, visual_results):
        visual_metadata = None
        if visual_route.get("visualType") and visual_result.get("success"):
            visual_config = dict(visual_route.get("visualConfig") or {})
            visual_config["generatedData"] = visual_result.get("data", {})
            visual_metadata = VisualMetadata(
                visualType=visual_route.get("visualType"),
                visualConfig=visual_config,
                confidence=visual_route.get("confidence"),
                generatedBy=visual_route.get("generatedBy"),
                reasoning=visual_route.get("reasoning"),
            )

        fallback_slides.append(
            Slide(
                title=slide_data.get("title", "Untitled"),
                content=slide_data.get("content", ""),
                order=slide_data.get("order", 0),
                visualMetadata=visual_metadata,
            )
        )

    return _lesson_from_payload(
        slides_data=result.get("slides", []),
        topic=result.get("title") or topic,
        subject=request.subject,
        grade_level=request.gradeLevel,
        theme=request.theme,
        fallback_slides=fallback_slides,
    )

# ... (generate_deck function stays here, simplified for brevity in this replace block if not editing it) ...

@router.post("/modify-deck", response_model=DeckGenerateResponse)
async def modify_deck(request: DeckModifyRequest):
    """Modify an existing deck based on user feedback"""
    try:
        return await _build_modified_deck_response(
            current_deck=request.currentDeck,
            feedback=request.feedback,
            subject=request.subject,
            grade_level=request.gradeLevel,
        )

    except Exception as e:
        logger.error(f"Deck modification failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to modify deck: {str(e)}")


@router.post("/regenerate-cluster", response_model=DeckGenerateResponse)
async def regenerate_cluster(request: DeckRegenerateClusterRequest):
    """Regenerate a specific structured cluster with one additional role-aligned slide."""
    try:
        cluster_slides = [
            slide for slide in ((request.currentDeck.get("lesson", {}) or {}).get("slides", []))
            if slide.get("clusterId") == request.clusterId
        ]
        cluster_titles = ", ".join(slide.get("title", "Untitled") for slide in cluster_slides) or request.clusterId
        feedback = (
            f'Add exactly one new slide to cluster "{request.clusterId}" for pedagogical role "{request.pedagogicalRole}". '
            f'Target the cluster slides titled {cluster_titles}. Preserve all existing slides, their order, and all structured metadata '
            'fields such as clusterId, pedagogicalRole, instructionalGoal, contentMode, contentBlocks, layoutCandidates, visualIntent, '
            'editingHints, and practiceMetadata. Keep the new slide in the same cluster and aligned to the existing theme.'
        )

        return await _build_modified_deck_response(
            current_deck=request.currentDeck,
            feedback=feedback,
            subject=request.subject,
            grade_level=request.gradeLevel,
            theme=request.theme,
        )
    except Exception as e:
        logger.error(f"Cluster regeneration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to regenerate cluster: {str(e)}")


@router.post("/generate-deck", response_model=DeckGenerateResponse)
async def generate_deck(request: DeckGenerateRequest):
    """Generate a teaching deck using AI with structured topic sequence"""
    try:
        topics_list = request.topics if request.topics else [request.topic] if request.topic else []
        if not topics_list:
            raise HTTPException(status_code=400, detail="No topics provided")

        topics_list = [str(topic) for topic in topics_list if topic]

        if request.structuredFormat or len(topics_list) > 1:
            lesson_deck = await _generate_planned_lesson_deck(request)
        else:
            lesson_deck = await _generate_legacy_lesson_deck(request, topics_list)

        return _build_response(
            lesson_deck,
            title=request.topic or ", ".join(str(topic) for topic in topics_list if topic),
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
        topics_list = request.topics if request.topics else [request.topic] if request.topic else []
        topics_list = [str(topic) for topic in topics_list if topic]
        if not topics_list:
            raise HTTPException(status_code=400, detail="No topics provided")

        from app.models.lesson_schema import DifferentiationLevel

        if request.structuredFormat or len(topics_list) > 1:
            lesson_deck = await _generate_planned_lesson_deck(request)
        else:
            lesson_deck = await _generate_legacy_lesson_deck(request, topics_list)

        # Step 3.5: Differentiate if requested
        if request.level and request.level != DifferentiationLevel.CORE:
            logger.info(f"[PPTX EXPORT] Differentiating to level: {request.level}")
            from app.services.differentiation import DifferentiationService
            diff_service = DifferentiationService()
            lesson_deck = await diff_service.generate_differentiated_deck(
                core_deck=lesson_deck,
                target_level=request.level
            )

        lesson_deck = apply_quality_guards_to_lesson(lesson_deck)
        
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


@router.post("/render-pptx")
async def render_pptx(request: PPTXRenderRequest):
    """Render an already-constructed canonical lesson deck to PPTX."""
    try:
        lesson_deck = apply_quality_guards_to_lesson(request.lesson)
        theme = request.theme or lesson_deck.meta.theme or "default"
        renderer = PPTXRenderer(theme=theme)
        pptx_file = await renderer.render_lesson_deck(lesson_deck)
        filename = f"{lesson_deck.meta.topic or 'lesson'}_deck.pptx".replace(" ", "_")

        return StreamingResponse(
            pptx_file,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error(f"PPTX render failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to render PPTX: {str(e)}")


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
        lesson_deck = await _generate_planned_lesson_deck(request)

        level_value = request.level.value if hasattr(request.level, 'value') else str(request.level) if request.level else 'CORE'
        level_value = level_value.upper()
        logger.info(f"[DEBUG] Checking differentiation - level_value: {level_value}")

        if level_value != 'CORE':
            logger.info(f"[Step 4/4] Applying differentiation for level: {level_value}")
            try:
                from app.services.differentiation import DifferentiationService, DifferentiationLevel as DiffLevel
                diff_service = DifferentiationService()

                level_map = {
                    'SUPPORT': DiffLevel.SUPPORT,
                    'EXTENSION': DiffLevel.EXTENSION,
                }
                target_level = level_map.get(level_value)

                if target_level:
                    lesson_deck = await diff_service.generate_differentiated_deck(
                        core_deck=lesson_deck,
                        target_level=target_level
                    )
                    logger.info(f"✓ Differentiation applied: {len(lesson_deck.slides)} slides for {level_value}")
                else:
                    logger.warning(f"Unknown level '{level_value}', using core slides")
            except Exception as diff_error:
                logger.warning(f"Differentiation failed, returning core: {str(diff_error)}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.info("[Step 4/4] Level is CORE, skipping differentiation")

        level_suffix = f" ({level_value})" if level_value != 'CORE' else ""
        title = (request.topic or ", ".join(request.topics) if request.topics else "Teaching Deck") + level_suffix
        return _serialize_lesson_deck_payload(lesson_deck, title=title)
        
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
        
        # Step 1: Generate CORE deck using planner-driven pipeline
        logger.info("[Step 1/3] Generating CORE deck...")
        from app.services.differentiation import DifferentiationService, DifferentiationLevel
        core_deck = await _generate_planned_lesson_deck(request)
        
        logger.info(f"✓ CORE deck created: {len(core_deck.slides)} slides")
        
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
        from app.services.differentiation import DifferentiationService
        core_deck = await _generate_planned_lesson_deck(request)
        
        diff_service = DifferentiationService()
        differentiated_deck = await diff_service.generate_differentiated_deck(
            core_deck=core_deck,
            target_level=target_level
        )
        
        logger.info(f"✓ {target_level} deck generated with {len(differentiated_deck.slides)} slides")
        
        title = f"{request.topic or ', '.join(request.topics)} ({target_level.value})"
        return _serialize_lesson_deck_payload(differentiated_deck, title=title)
        
    except Exception as e:
        logger.error(f"[LEVEL GENERATION] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Level generation failed: {str(e)}")


# ===== ADD ACTIVITY ENDPOINT =====

from pydantic import BaseModel
from typing import Optional

class AddActivityRequest(BaseModel):
    """Request to generate an activity slide"""
    slideContext: dict  # title, content of the preceding slide
    activityType: str   # mcq, short-answer, long-answer, fill-in-blank
    customPrompt: Optional[str] = None  # Optional custom instructions
    subject: str
    gradeLevel: str
    topic: str

class AddActivityResponse(BaseModel):
    """Response with generated activity content"""
    title: str
    content: str
    bloom_level: str


@router.post("/add-activity", response_model=AddActivityResponse)
async def add_activity(request: AddActivityRequest):
    """
    Generate an activity (question) slide based on the context of a preceding slide.
    
    Activity types:
    - mcq: Multiple choice question with 4 options
    - short-answer: Short answer question (1-2 sentences)
    - long-answer: Long answer question (paragraph response)
    - fill-in-blank: Fill in the blank question
    """
    try:
        logger.info(f"[ADD ACTIVITY] Generating {request.activityType} activity for topic: {request.topic}")
        
        # Map activity type to prompt instructions
        activity_instructions = {
            'mcq': '''Generate a multiple-choice question with:
- A clear, grade-appropriate question
- 4 options labeled A, B, C, D
- The correct answer indicated
- Brief explanation of why the answer is correct''',
            'short-answer': '''Generate a short-answer question that:
- Tests understanding of the key concept
- Can be answered in 1-2 sentences
- Include the expected answer''',
            'long-answer': '''Generate a long-answer question that:
- Requires deeper analysis or explanation
- Encourages critical thinking
- Include key points expected in the answer''',
            'fill-in-blank': '''Generate a fill-in-the-blank question that:
- Has 1-2 blanks for key terms
- Tests recall of important vocabulary or concepts
- Include the correct answers for each blank'''
        }
        
        activity_instruction = activity_instructions.get(
            request.activityType, 
            activity_instructions['mcq']
        )
        
        system_message = f"""You are an expert educator creating assessment activities for {request.gradeLevel} students studying {request.subject}.
Generate engaging, pedagogically sound activities that align with Bloom's Taxonomy.
Always return a valid JSON object with: title, content, bloom_level (one of: REMEMBER, UNDERSTAND, APPLY, ANALYZE, EVALUATE, CREATE)."""
        
        prompt = f"""Create an activity based on this slide content:

TOPIC: {request.topic}
SLIDE TITLE: {request.slideContext.get('title', '')}
SLIDE CONTENT: {request.slideContext.get('content', '')}

ACTIVITY TYPE: {request.activityType}

{activity_instruction}

{f'ADDITIONAL INSTRUCTIONS: {request.customPrompt}' if request.customPrompt else ''}

Return JSON:
{{
    "title": "Activity title (descriptive, engaging)",
    "content": "The complete activity content formatted cleanly",
    "bloom_level": "The cognitive level this activity targets"
}}"""
        
        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=1000,
            temperature=0.7
        )
        
        logger.info(f"✓ Activity generated: {result.get('title', 'Unknown')}")
        
        return AddActivityResponse(
            title=result.get('title', f'{request.activityType.upper()} Activity'),
            content=result.get('content', ''),
            bloom_level=result.get('bloom_level', 'APPLY')
        )
        
    except Exception as e:
        logger.error(f"[ADD ACTIVITY] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Activity generation failed: {str(e)}")


# ===== ADD SLIDE ENDPOINT =====

class AddSlideRequest(BaseModel):
    """Request to generate a new slide"""
    description: str    # Teacher's description of what they want
    slideType: str      # CONCEPT, ACTIVITY, ASSESSMENT, SUMMARY
    subject: str
    gradeLevel: str
    topic: str

class AddSlideResponse(BaseModel):
    """Response with generated slide content"""
    title: str
    content: str
    bloom_level: str


@router.post("/add-slide", response_model=AddSlideResponse)
async def add_slide(request: AddSlideRequest):
    """
    Generate a new slide based on teacher's description.
    
    Slide types:
    - CONCEPT: Explanatory content teaching a concept
    - ACTIVITY: Interactive activity or practice
    - ASSESSMENT: Quiz or assessment questions
    - SUMMARY: Recap or summary of key points
    """
    try:
        logger.info(f"[ADD SLIDE] Generating {request.slideType} slide for topic: {request.topic}")
        
        # Map slide type to Bloom's level suggestions
        type_bloom_map = {
            'CONCEPT': 'UNDERSTAND',
            'ACTIVITY': 'APPLY',
            'ASSESSMENT': 'ANALYZE',
            'SUMMARY': 'REMEMBER'
        }
        
        suggested_bloom = type_bloom_map.get(request.slideType, 'UNDERSTAND')
        
        system_message = f"""You are an expert instructional designer creating educational slides for {request.gradeLevel} students studying {request.subject}.
Create engaging, educationally sound content that:
- Is age-appropriate for {request.gradeLevel}
- Uses clear, simple language
- Includes concrete examples when helpful
- Follows best practices for visual learning

Always return a valid JSON object with: title, content, bloom_level."""
        
        prompt = f"""Create a {request.slideType} slide for this lesson:

TOPIC: {request.topic}
SUBJECT: {request.subject}
GRADE LEVEL: {request.gradeLevel}

TEACHER'S REQUEST:
{request.description}

SLIDE TYPE: {request.slideType}
SUGGESTED BLOOM LEVEL: {suggested_bloom}

Guidelines for {request.slideType} slides:
- CONCEPT: Clear explanation with examples, bullet points for key ideas
- ACTIVITY: Interactive task or practice exercise
- ASSESSMENT: Questions to check understanding
- SUMMARY: Key takeaways and recap

Return JSON:
{{
    "title": "Slide title (clear, concise, engaging)",
    "content": "Slide content formatted as bullet points where appropriate",
    "bloom_level": "The cognitive level this slide targets"
}}"""
        
        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=1000,
            temperature=0.7
        )
        
        logger.info(f"✓ Slide generated: {result.get('title', 'Unknown')}")

        return AddSlideResponse(
            title=result.get('title', 'New Slide'),
            content=result.get('content', ''),
            bloom_level=result.get('bloom_level', suggested_bloom)
        )
        
    except Exception as e:
        logger.error(f"[ADD SLIDE] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Slide generation failed: {str(e)}")
