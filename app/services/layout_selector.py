from __future__ import annotations

from dataclasses import dataclass

from app.models.lesson_schema import EditingHints, Slide
from app.services.layout_registry import LAYOUT_REGISTRY, LayoutSpec
from app.services.visual_policy import (
    allowed_visual_families_for_slide,
    classify_concept_type,
)
from app.services.visual_quality import VisualQualityStatus, score_visual_candidate


class LayoutSelectionError(ValueError):
    pass


VISUAL_STATE_KEPT = "visual_kept"
VISUAL_STATE_REJECTED = "visual_rejected"


@dataclass(frozen=True)
class SelectedLayout:
    layout_id: str
    theme: str


def _has_required_blocks(slide: Slide, spec: LayoutSpec) -> bool:
    block_types = {block.type for block in slide.contentBlocks}
    return all(required in block_types for required in spec.required_blocks)


def _has_visual_asset(slide: Slide) -> bool:
    if slide.visualIntent is None:
        return False
    return str(slide.visualIntent.assetType).lower() != "none"


def _can_render_image_layout(slide: Slide) -> bool:
    return bool(slide.imageQuery and _has_real_visual(slide))


def _has_real_visual(slide: Slide) -> bool:
    return bool(slide.visualMetadata and slide.visualMetadata.visualType)


def mark_visual_outcome(slide: Slide, outcome: str) -> None:
    editing_hints = slide.editingHints or EditingHints()
    notes = dict(editing_hints.notes or {})
    notes["visual_state"] = outcome
    slide.editingHints = editing_hints.model_copy(
        update={"notes": notes}
    )


def get_visual_outcome(slide: Slide) -> str | None:
    editing_hints = slide.editingHints
    if not editing_hints:
        return None
    return (editing_hints.notes or {}).get("visual_state")


def _has_renderable_visual_asset(slide: Slide, spec: LayoutSpec) -> bool:
    if spec.visual_family in {"editorial_image", "real_world_photo"}:
        return _can_render_image_layout(slide)

    metadata = slide.visualMetadata
    visual_type = metadata.visualType if metadata else None
    if spec.visual_family == "annotated_chart":
        return visual_type == "chart"
    if spec.visual_family == "equation":
        return visual_type in {"math", "equation"}
    if spec.visual_family in {"process_diagram", "labeled_explainer", "comparison_visual", "summary_recap"}:
        return bool(visual_type)
    return False


def _visual_status_for_slide(slide: Slide, spec: LayoutSpec) -> VisualQualityStatus | None:
    if not spec.visual_family:
        return None

    concept_type = classify_concept_type(slide)
    allowed_families = allowed_visual_families_for_slide(slide, concept_type)
    quality = score_visual_candidate(
        allowed_families=allowed_families,
        candidate_family=spec.visual_family,
        has_renderable_asset=_has_renderable_visual_asset(slide, spec),
        query_text=slide.imageQuery,
    )

    if quality.status == VisualQualityStatus.STRONG:
        mark_visual_outcome(slide, VISUAL_STATE_KEPT)
    else:
        mark_visual_outcome(slide, VISUAL_STATE_REJECTED)

    return quality.status


def _prioritized_candidates(
    slide: Slide, theme_layouts: dict[str, LayoutSpec]
) -> list[str]:
    visual_candidates: list[str] = []
    fallback_candidates: list[str] = []
    rejected_visual_candidates: list[str] = []

    for candidate in slide.layoutCandidates:
        spec = theme_layouts.get(candidate)
        if not spec:
            continue

        visual_status = _visual_status_for_slide(slide, spec)
        if visual_status == VisualQualityStatus.STRONG:
            visual_candidates.append(candidate)
            continue
        if visual_status == VisualQualityStatus.REJECT:
            rejected_visual_candidates.append(candidate)
            continue

        fallback_candidates.append(candidate)

    if visual_candidates:
        return visual_candidates + fallback_candidates

    if rejected_visual_candidates and fallback_candidates:
        return fallback_candidates

    return fallback_candidates + rejected_visual_candidates


def _matches_layout(slide: Slide, spec: LayoutSpec) -> bool:
    role = slide.pedagogicalRole.value if slide.pedagogicalRole else None
    mode = slide.contentMode.value if slide.contentMode else None

    if role not in spec.roles:
        return False
    if mode not in spec.content_modes:
        return False
    if not _has_required_blocks(slide, spec):
        return False
    if spec.max_blocks is not None and len(slide.contentBlocks) > spec.max_blocks:
        return False
    if spec.requires_visual_asset and not _has_visual_asset(slide):
        return False
    if spec.visual_family and get_visual_outcome(slide) == VISUAL_STATE_REJECTED:
        return False
    if spec.requires_visual_asset and not _can_render_image_layout(slide):
        return False
    return True


def select_layout_for_slide(slide: Slide, theme: str) -> SelectedLayout:
    theme_layouts = LAYOUT_REGISTRY.get(theme, LAYOUT_REGISTRY["default"])

    for candidate in _prioritized_candidates(slide, theme_layouts):
        spec = theme_layouts.get(candidate)
        if spec and _matches_layout(slide, spec):
            return SelectedLayout(layout_id=candidate, theme=theme)

    raise LayoutSelectionError(f"No valid layout candidates for slide {slide.title}")
