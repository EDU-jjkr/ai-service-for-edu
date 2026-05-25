from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.models.lesson_schema import ContentBlock, ContentMode, EditingHints, LessonDeck, Slide


GENERIC_PHRASES = (
    "learn about",
    "understand the concept",
    "important topic",
    "this slide explains",
    "in this lesson",
)

MAX_POINTS_BY_DENSITY = {
    "low": 3,
    "medium": 5,
    "high": 7,
}


@dataclass(frozen=True)
class SlideQualityResult:
    score: int
    warnings: List[str]
    requires_regeneration: bool


def _clean_items(items: List[str]) -> List[str]:
    return [item.strip() for item in items if item and item.strip()]


def _slide_density_key(slide: Slide) -> str:
    if slide.density:
        return slide.density.value if hasattr(slide.density, "value") else str(slide.density)
    return "medium"


def _max_points_for_slide(slide: Slide) -> int:
    return MAX_POINTS_BY_DENSITY.get(_slide_density_key(slide), 5)


def _text_for_generic_scan(slide: Slide) -> str:
    parts = [slide.title, slide.content, slide.instructionalGoal or "", slide.objective or ""]
    for block in slide.contentBlocks:
        if block.text:
            parts.append(block.text)
        parts.extend(block.items)
    return " ".join(parts).lower()


def _flatten_support_points(slide: Slide) -> List[str]:
    points: List[str] = []
    for block in slide.contentBlocks:
        if block.type in {"bullets", "steps", "takeaway", "hint", "example", "callout", "subhead"}:
            if block.text:
                points.append(block.text.strip())
            points.extend(_clean_items(block.items))
    if points:
        return points
    return [line.strip() for line in slide.content.splitlines() if line.strip()]


def evaluate_slide_quality(slide: Slide) -> SlideQualityResult:
    warnings: List[str] = []
    score = 100
    support_points = _flatten_support_points(slide)
    point_count = len(support_points)
    max_points = _max_points_for_slide(slide)

    if point_count > max_points:
        warnings.append("over_dense_support")
        score -= min(25, (point_count - max_points) * 6)

    scan_text = _text_for_generic_scan(slide)
    if any(phrase in scan_text for phrase in GENERIC_PHRASES):
        warnings.append("generic_language")
        score -= 15

    if slide.contentMode == ContentMode.QUESTION and not any(block.type == "question" for block in slide.contentBlocks):
        warnings.append("missing_question_block")
        score -= 30

    if slide.contentMode == ContentMode.IMAGE_SUPPORT and slide.editingHints and (slide.editingHints.notes or {}).get("visual_state") == "visual_rejected":
        warnings.append("text_first_fallback")

    score = max(score, 0)
    requires_regeneration = any(
        warning in {"generic_language", "missing_question_block"} for warning in warnings
    ) or score < 65

    return SlideQualityResult(score=score, warnings=warnings, requires_regeneration=requires_regeneration)


def _trim_block_items(block: ContentBlock, allowed_count: int) -> ContentBlock:
    cleaned_items = _clean_items(block.items)
    if block.type in {"bullets", "steps", "takeaway", "hint", "example"} and len(cleaned_items) > allowed_count:
        return block.model_copy(update={"items": cleaned_items[:allowed_count]})
    return block.model_copy(update={"items": cleaned_items})


def apply_quality_guards_to_slide(slide: Slide) -> Slide:
    allowed_count = _max_points_for_slide(slide)
    updated_blocks: List[ContentBlock] = []
    remaining_allowance = allowed_count
    trim_applied = False

    for block in slide.contentBlocks:
        original_items = _clean_items(block.items)
        normalized = _trim_block_items(block, max(remaining_allowance, 0))
        updated_blocks.append(normalized)
        if normalized.type in {"bullets", "steps", "takeaway", "hint", "example"}:
            if len(normalized.items) < len(original_items):
                trim_applied = True
            remaining_allowance -= len(normalized.items)

    result = evaluate_slide_quality(slide.model_copy(update={"contentBlocks": updated_blocks}))
    warnings = list(result.warnings)
    if trim_applied and "over_dense_support" not in warnings:
        warnings.insert(0, "over_dense_support")

    editing_hints = slide.editingHints or EditingHints()
    notes = dict(editing_hints.notes or {})
    notes["quality_score"] = result.score
    notes["quality_warnings"] = warnings
    notes["requires_regeneration"] = result.requires_regeneration

    return slide.model_copy(
        update={
            "contentBlocks": updated_blocks,
            "editingHints": editing_hints.model_copy(update={"notes": notes}),
        }
    )


def apply_quality_guards_to_lesson(lesson_deck: LessonDeck) -> LessonDeck:
    guarded_slides = [apply_quality_guards_to_slide(slide) for slide in lesson_deck.slides]
    return lesson_deck.model_copy(update={"slides": guarded_slides})
