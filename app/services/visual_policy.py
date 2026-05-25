from __future__ import annotations

from app.models.lesson_schema import ContentMode, PedagogicalRole, Slide


def classify_concept_type(slide: Slide) -> str:
    role = slide.pedagogicalRole
    if role in {
        PedagogicalRole.GUIDED_PRACTICE,
        PedagogicalRole.INDEPENDENT_PRACTICE,
    }:
        return "practice"

    mode = slide.contentMode
    if mode == ContentMode.COMPARISON:
        return "comparison"
    if mode in {ContentMode.EQUATION, ContentMode.CHART}:
        return "quantitative"

    block_types = {block.type for block in (slide.contentBlocks or [])}
    if "steps" in block_types:
        return "process"

    return "observational"


def allowed_visual_families_for_slide(
    slide: Slide, concept_type: str
) -> tuple[str, ...]:
    role = slide.pedagogicalRole

    if role == PedagogicalRole.HOOK:
        if concept_type == "observational":
            return ("editorial_image", "real_world_photo")
        return ("labeled_explainer",)

    if role in {
        PedagogicalRole.EXPLAIN_CORE,
        PedagogicalRole.EXPLAIN_DEEPEN,
    }:
        if concept_type == "process":
            return ("process_diagram", "labeled_explainer")
        if concept_type == "quantitative":
            return ("equation", "annotated_chart")
        if concept_type == "comparison":
            return ("comparison_visual", "labeled_explainer")
        return ("labeled_explainer",)

    if role == PedagogicalRole.WORKED_EXAMPLE:
        return ("equation", "annotated_chart", "process_diagram")

    if role == PedagogicalRole.COMPARE_EXAMPLE:
        return ("comparison_visual", "labeled_explainer")

    if role in {
        PedagogicalRole.GUIDED_PRACTICE,
        PedagogicalRole.INDEPENDENT_PRACTICE,
    }:
        return ("none",)

    if role == PedagogicalRole.SUMMARY:
        return ("none", "summary_recap")

    return ("none",)
