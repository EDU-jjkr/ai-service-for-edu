from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutSpec:
    roles: tuple[str, ...]
    content_modes: tuple[str, ...]
    required_blocks: tuple[str, ...]
    requires_visual_asset: bool = False
    visual_family: str | None = None
    max_blocks: int | None = None


DEFAULT_LAYOUTS: dict[str, LayoutSpec] = {
    "concept-focus": LayoutSpec(
        roles=("explain_core", "explain_deepen"),
        content_modes=("text_only", "equation", "image_support"),
        required_blocks=("headline",),
        max_blocks=6,
    ),
    "concept-with-image": LayoutSpec(
        roles=("hook", "explain_core"),
        content_modes=("image_support",),
        required_blocks=("headline",),
        requires_visual_asset=True,
        visual_family="editorial_image",
    ),
    "worked-example": LayoutSpec(
        roles=("worked_example",),
        content_modes=("comparison", "equation"),
        required_blocks=("headline", "steps"),
    ),
    "guided-practice": LayoutSpec(
        roles=("guided_practice",),
        content_modes=("question",),
        required_blocks=("question",),
    ),
    "independent-practice": LayoutSpec(
        roles=("independent_practice",),
        content_modes=("question",),
        required_blocks=("question",),
    ),
    "summary-grid": LayoutSpec(
        roles=("summary",),
        content_modes=("text_only",),
        required_blocks=("takeaway",),
    ),
}


LAYOUT_REGISTRY: dict[str, dict[str, LayoutSpec]] = {
    "default": DEFAULT_LAYOUTS,
}
