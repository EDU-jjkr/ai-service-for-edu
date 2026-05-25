from app.models.lesson_schema import (
    BloomLevel,
    ContentBlock,
    ContentMode,
    DensityLevel,
    EditingHints,
    ImportanceLevel,
    PedagogicalRole,
    PracticeMetadata,
    Slide,
    SlideType,
    VisualIntent,
    VisualPriority,
    VisualSourceStrategy,
)
from app.services.lesson_narrative_planner import LessonNarrativePlan


ROLE_MAP = {
    "hook": {
        "role": PedagogicalRole.HOOK,
        "mode": ContentMode.IMAGE_SUPPORT,
        "layouts": ["title-hero", "concept-with-image"],
        "slide_type": SlideType.INTRODUCTION,
        "bloom_level": BloomLevel.REMEMBER,
        "density": DensityLevel.LOW,
        "importance": ImportanceLevel.PRIMARY,
        "visual_intent": VisualIntent(
            purpose="motivate",
            assetType="photo",
            priority=VisualPriority.REQUIRED,
            sourceStrategy=VisualSourceStrategy.STOCK,
        ),
    },
    "explain": {
        "role": PedagogicalRole.EXPLAIN_CORE,
        "mode": ContentMode.TEXT_ONLY,
        "layouts": ["concept-focus", "two-column-explain"],
        "slide_type": SlideType.CONCEPT,
        "bloom_level": BloomLevel.UNDERSTAND,
        "density": DensityLevel.MEDIUM,
        "importance": ImportanceLevel.PRIMARY,
        "visual_intent": VisualIntent(
            purpose="clarify",
            assetType="none",
            priority=VisualPriority.OPTIONAL,
            sourceStrategy=VisualSourceStrategy.RENDERER_NATIVE,
        ),
    },
    "example": {
        "role": PedagogicalRole.WORKED_EXAMPLE,
        "mode": ContentMode.COMPARISON,
        "layouts": ["worked-example", "compare-example"],
        "slide_type": SlideType.CONCEPT,
        "bloom_level": BloomLevel.APPLY,
        "density": DensityLevel.MEDIUM,
        "importance": ImportanceLevel.PRIMARY,
        "visual_intent": VisualIntent(
            purpose="clarify",
            assetType="diagram",
            priority=VisualPriority.OPTIONAL,
            sourceStrategy=VisualSourceStrategy.DIAGRAMMATIC,
        ),
    },
    "guided_practice": {
        "role": PedagogicalRole.GUIDED_PRACTICE,
        "mode": ContentMode.QUESTION,
        "layouts": ["guided-practice"],
        "slide_type": SlideType.ACTIVITY,
        "bloom_level": BloomLevel.APPLY,
        "density": DensityLevel.MEDIUM,
        "importance": ImportanceLevel.PRIMARY,
        "visual_intent": VisualIntent(
            purpose="practice",
            assetType="none",
            priority=VisualPriority.OPTIONAL,
            sourceStrategy=VisualSourceStrategy.RENDERER_NATIVE,
        ),
    },
    "independent_practice": {
        "role": PedagogicalRole.INDEPENDENT_PRACTICE,
        "mode": ContentMode.QUESTION,
        "layouts": ["independent-practice"],
        "slide_type": SlideType.ASSESSMENT,
        "bloom_level": BloomLevel.ANALYZE,
        "density": DensityLevel.MEDIUM,
        "importance": ImportanceLevel.PRIMARY,
        "visual_intent": VisualIntent(
            purpose="assess",
            assetType="none",
            priority=VisualPriority.OPTIONAL,
            sourceStrategy=VisualSourceStrategy.RENDERER_NATIVE,
        ),
    },
    "summary": {
        "role": PedagogicalRole.SUMMARY,
        "mode": ContentMode.TEXT_ONLY,
        "layouts": ["summary-grid"],
        "slide_type": SlideType.SUMMARY,
        "bloom_level": BloomLevel.CREATE,
        "density": DensityLevel.LOW,
        "importance": ImportanceLevel.SECONDARY,
        "visual_intent": VisualIntent(
            purpose="synthesize",
            assetType="none",
            priority=VisualPriority.OPTIONAL,
            sourceStrategy=VisualSourceStrategy.RENDERER_NATIVE,
        ),
    },
}


def _build_title(cluster_kind: str, subtopic: str, slide_index: int) -> str:
    base = cluster_kind.replace("_", " ").title()
    if cluster_kind == "hook":
        return f"Why {subtopic} Matters"
    if cluster_kind == "summary":
        return f"{subtopic} Summary"
    if cluster_kind in {"guided_practice", "independent_practice"}:
        return f"{subtopic}: {base} {slide_index + 1}"
    return f"{subtopic}: {base} {slide_index + 1}"


def _build_blocks(cluster_kind: str, title: str) -> list[ContentBlock]:
    blocks = [ContentBlock(type="headline", text=title)]

    if cluster_kind == "guided_practice":
        blocks.append(ContentBlock(type="question", text="Solve with teacher support."))
    elif cluster_kind == "independent_practice":
        blocks.append(ContentBlock(type="question", text="Try this on your own."))
    elif cluster_kind == "summary":
        blocks.append(ContentBlock(type="takeaway", text="Summarize the main learning."))
    else:
        blocks.append(ContentBlock(type="body", text="Teaching content placeholder"))

    return blocks


def _build_practice_metadata(cluster_kind: str) -> PracticeMetadata | None:
    if cluster_kind == "guided_practice":
        return PracticeMetadata(
            difficulty="medium",
            answerMode="hidden_by_default",
            stepCount=3,
            misconception="Students may confuse support steps with the final answer.",
        )
    if cluster_kind == "independent_practice":
        return PracticeMetadata(
            difficulty="medium",
            answerMode="teacher_reference",
            stepCount=4,
            misconception="Students may skip showing their reasoning.",
        )
    return None


def _cluster_kind_from_outline(slide_outline: dict) -> str:
    slide_type = str(slide_outline.get("slideType", "CONCEPT")).upper()
    if slide_type == "INTRODUCTION":
        return "hook"
    if slide_type == "ACTIVITY":
        return "guided_practice"
    if slide_type == "ASSESSMENT":
        return "independent_practice"
    if slide_type == "SUMMARY":
        return "summary"
    return "explain"


def _build_shell_from_outline(slide_outline: dict, order: int, cluster_index: int) -> Slide:
    cluster_kind = _cluster_kind_from_outline(slide_outline)
    cluster_config = ROLE_MAP[cluster_kind]
    title = slide_outline.get("title", f"Slide {order}")
    objective = slide_outline.get("objective") or f"{cluster_kind.replace('_', ' ').title()} for {title}"

    return Slide(
        title=title,
        content=f"{cluster_kind} content placeholder",
        order=order,
        slideType=cluster_config["slide_type"],
        bloom_level=slide_outline.get("bloom_level", cluster_config["bloom_level"]),
        objective=objective,
        clusterId=f"{cluster_kind}_{cluster_index}",
        pedagogicalRole=cluster_config["role"],
        instructionalGoal=objective,
        contentMode=cluster_config["mode"],
        contentBlocks=_build_blocks(cluster_kind, title),
        layoutCandidates=list(cluster_config["layouts"]),
        density=cluster_config["density"],
        importance=cluster_config["importance"],
        visualIntent=cluster_config["visual_intent"].model_copy(deep=True),
        editingHints=EditingHints(
            locked=False,
            canAddBlocks=["hint", "example"],
            canRemoveBlocks=["answer"],
        ),
        practiceMetadata=_build_practice_metadata(cluster_kind),
    )


def build_structured_slides_from_plan(
    plan: LessonNarrativePlan,
    subject: str,
    grade_level: str,
) -> list[Slide]:
    slides: list[Slide] = []
    order = 1

    del subject
    del grade_level

    for cluster_index, cluster in enumerate(plan.clusters, start=1):
        cluster_config = ROLE_MAP[cluster.kind]
        subtopic = cluster.subtopics[0] if cluster.subtopics else cluster.kind.replace("_", " ").title()

        for slide_index in range(cluster.slide_count):
            title = _build_title(cluster.kind, subtopic, slide_index)
            slide = Slide(
                title=title,
                content=f"{cluster.kind} content placeholder",
                order=order,
                slideType=cluster_config["slide_type"],
                bloom_level=cluster_config["bloom_level"],
                objective=f"{cluster.kind.replace('_', ' ').title()} for {subtopic}",
                clusterId=f"{cluster.kind}_{cluster_index}",
                pedagogicalRole=cluster_config["role"],
                instructionalGoal=f"Help students engage with {subtopic} through {cluster.kind.replace('_', ' ')}.",
                contentMode=cluster_config["mode"],
                contentBlocks=_build_blocks(cluster.kind, title),
                layoutCandidates=list(cluster_config["layouts"]),
                density=cluster_config["density"],
                importance=cluster_config["importance"],
                visualIntent=cluster_config["visual_intent"].model_copy(deep=True),
                editingHints=EditingHints(
                    locked=False,
                    canAddBlocks=["hint", "example"],
                    canRemoveBlocks=["answer"],
                ),
                practiceMetadata=_build_practice_metadata(cluster.kind),
            )
            slides.append(slide)
            order += 1

    return slides


def expand_structured_slides_to_outline(
    structured_slides: list[Slide],
    outline: list[dict],
) -> list[Slide]:
    if len(outline) <= len(structured_slides):
        return structured_slides

    expanded_slides = [slide.model_copy(deep=True) for slide in structured_slides]
    for index, slide_outline in enumerate(outline[len(expanded_slides):], start=len(expanded_slides) + 1):
        expanded_slides.append(
            _build_shell_from_outline(
                slide_outline=slide_outline,
                order=index,
                cluster_index=index,
            )
        )

    return expanded_slides
