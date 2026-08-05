from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VisualQualityStatus(str, Enum):
    NOT_NEEDED = "not_needed"
    REJECT = "reject"
    STRONG = "strong"


class VisualQualityReason(str, Enum):
    ACCEPTED = "accepted"
    ASSET_MISSING = "asset_missing"
    FAMILY_NOT_ALLOWED = "family_not_allowed"
    QUERY_TOO_GENERIC = "query_too_generic"
    VISUAL_NOT_NEEDED = "visual_not_needed"


@dataclass(frozen=True)
class VisualQualityResult:
    status: VisualQualityStatus
    reason: VisualQualityReason
    chosen_family: str


def score_visual_candidate(
    *,
    allowed_families: tuple[str, ...],
    candidate_family: str | None,
    has_renderable_asset: bool,
    query_text: str | None,
) -> VisualQualityResult:
    if "none" in allowed_families and not candidate_family:
        return VisualQualityResult(
            status=VisualQualityStatus.NOT_NEEDED,
            reason=VisualQualityReason.VISUAL_NOT_NEEDED,
            chosen_family="none",
        )

    if not candidate_family or candidate_family not in allowed_families:
        return VisualQualityResult(
            status=VisualQualityStatus.REJECT,
            reason=VisualQualityReason.FAMILY_NOT_ALLOWED,
            chosen_family="none",
        )

    if not has_renderable_asset:
        return VisualQualityResult(
            status=VisualQualityStatus.REJECT,
            reason=VisualQualityReason.ASSET_MISSING,
            chosen_family="none",
        )

    if candidate_family in {"editorial_image", "real_world_photo"}:
        if len((query_text or "").strip()) < 12:
            return VisualQualityResult(
                status=VisualQualityStatus.REJECT,
                reason=VisualQualityReason.QUERY_TOO_GENERIC,
                chosen_family="none",
            )

    return VisualQualityResult(
        status=VisualQualityStatus.STRONG,
        reason=VisualQualityReason.ACCEPTED,
        chosen_family=candidate_family,
    )
