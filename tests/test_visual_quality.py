import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.lesson_schema import (
    ContentBlock,
    ContentMode,
    PedagogicalRole,
    Slide,
    VisualIntent,
    VisualPriority,
    VisualSourceStrategy,
)
from app.services.visual_policy import (
    allowed_visual_families_for_slide,
    classify_concept_type,
)
from app.services.visual_quality import (
    VisualQualityReason,
    VisualQualityStatus,
    score_visual_candidate,
)


def test_explain_process_slide_prefers_instructional_visuals():
    slide = Slide(
        title="Water Cycle",
        content="Evaporation, condensation, precipitation",
        order=1,
        clusterId="explain_1",
        pedagogicalRole=PedagogicalRole.EXPLAIN_CORE,
        contentMode=ContentMode.DIAGRAM,
        contentBlocks=[
            ContentBlock(type="steps", items=["Evaporation", "Condensation"])
        ],
        visualIntent=VisualIntent(
            purpose="explain",
            assetType="diagram",
            priority=VisualPriority.REQUIRED,
            sourceStrategy=VisualSourceStrategy.DIAGRAMMATIC,
        ),
    )

    concept_type = classify_concept_type(slide)
    families = allowed_visual_families_for_slide(slide, concept_type)

    assert concept_type == "process"
    assert "process_diagram" in families
    assert "editorial_image" not in families


def test_guided_practice_defaults_to_text_first_when_no_visual_dependency():
    slide = Slide(
        title="Try It",
        content="Solve the equation",
        order=2,
        clusterId="practice_1",
        pedagogicalRole=PedagogicalRole.GUIDED_PRACTICE,
        contentMode=ContentMode.QUESTION,
        contentBlocks=[ContentBlock(type="question", text="Solve 2x + 3 = 11")],
    )

    concept_type = classify_concept_type(slide)
    families = allowed_visual_families_for_slide(slide, concept_type)

    assert concept_type == "practice"
    assert families == ("none",)


def test_compare_example_explicitly_allows_comparison_visuals():
    slide = Slide(
        title="Plant vs Animal Cells",
        content="Compare key structures",
        order=3,
        clusterId="compare_1",
        pedagogicalRole=PedagogicalRole.COMPARE_EXAMPLE,
        contentMode=ContentMode.COMPARISON,
        contentBlocks=[
            ContentBlock(type="headline", text="Compare the two cell types")
        ],
    )

    concept_type = classify_concept_type(slide)
    families = allowed_visual_families_for_slide(slide, concept_type)

    assert concept_type == "comparison"
    assert families == ("comparison_visual", "labeled_explainer")


def test_unknown_role_falls_back_to_text_first_policy():
    slide = Slide(
        title="Observation",
        content="Notice the pattern",
        order=4,
        contentMode=ContentMode.TEXT_ONLY,
        contentBlocks=[ContentBlock(type="headline", text="Observe carefully")],
    )

    concept_type = classify_concept_type(slide)
    families = allowed_visual_families_for_slide(slide, concept_type)

    assert concept_type == "observational"
    assert families == ("none",)


def test_score_visual_candidate_accepts_allowed_renderable_visual():
    result = score_visual_candidate(
        allowed_families=("process_diagram", "labeled_explainer"),
        candidate_family="process_diagram",
        has_renderable_asset=True,
        query_text=None,
    )

    assert result.status == VisualQualityStatus.STRONG
    assert result.reason == VisualQualityReason.ACCEPTED
    assert result.chosen_family == "process_diagram"


def test_score_visual_candidate_returns_not_needed_when_policy_allows_none():
    result = score_visual_candidate(
        allowed_families=("none",),
        candidate_family=None,
        has_renderable_asset=False,
        query_text=None,
    )

    assert result.status == VisualQualityStatus.NOT_NEEDED
    assert result.reason == VisualQualityReason.VISUAL_NOT_NEEDED
    assert result.chosen_family == "none"


def test_score_visual_candidate_rejects_disallowed_family():
    result = score_visual_candidate(
        allowed_families=("labeled_explainer",),
        candidate_family="editorial_image",
        has_renderable_asset=True,
        query_text="water cycle diagram",
    )

    assert result.status == VisualQualityStatus.REJECT
    assert result.reason == VisualQualityReason.FAMILY_NOT_ALLOWED
    assert result.chosen_family == "none"


def test_score_visual_candidate_rejects_allowed_family_when_asset_missing():
    result = score_visual_candidate(
        allowed_families=("process_diagram", "labeled_explainer"),
        candidate_family="process_diagram",
        has_renderable_asset=False,
        query_text=None,
    )

    assert result.status == VisualQualityStatus.REJECT
    assert result.reason == VisualQualityReason.ASSET_MISSING
    assert result.chosen_family == "none"


def test_score_visual_candidate_accepts_summary_recap_from_mixed_family_policy():
    result = score_visual_candidate(
        allowed_families=("none", "summary_recap"),
        candidate_family="summary_recap",
        has_renderable_asset=True,
        query_text=None,
    )

    assert result.status == VisualQualityStatus.STRONG
    assert result.reason == VisualQualityReason.ACCEPTED
    assert result.chosen_family == "summary_recap"


def test_score_visual_candidate_rejects_generic_photo_query():
    result = score_visual_candidate(
        allowed_families=("editorial_image", "real_world_photo"),
        candidate_family="editorial_image",
        has_renderable_asset=True,
        query_text="friction",
    )

    assert result.status == VisualQualityStatus.REJECT
    assert result.reason == VisualQualityReason.QUERY_TOO_GENERIC
    assert result.chosen_family == "none"
