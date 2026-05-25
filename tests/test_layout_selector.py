import sys
import asyncio
from pathlib import Path

import pytest
from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.lesson_schema import (
    ContentBlock,
    ContentMode,
    EditingHints,
    LessonDeck,
    LessonMetadata,
    LearningStructure,
    PedagogicalRole,
    Slide,
    SlideType,
    VisualIntent,
    VisualMetadata,
)
from app.services.layout_registry import LAYOUT_REGISTRY
from app.services.layout_selector import LayoutSelectionError, select_layout_for_slide
from app.services.pptx_renderer import PPTXRenderer


def _build_test_lesson(slide: Slide, theme: str = "default") -> LessonDeck:
    return LessonDeck(
        meta=LessonMetadata(topic="Newton's Laws", subject="Physics", grade="9", theme=theme),
        structure=LearningStructure(
            learning_objectives=[],
            vocabulary=[],
            prerequisites=[],
            bloom_progression=[],
        ),
        slides=[slide],
    )


def _build_test_presentation():
    prs = Presentation()
    prs.slide_width = PPTXRenderer.render_lesson_deck.__globals__["SLIDE_W"]
    prs.slide_height = PPTXRenderer.render_lesson_deck.__globals__["SLIDE_H"]
    return prs


def test_selector_prefers_image_layout_for_image_support_slide():
    slide = Slide(
        title="Hook",
        content="Why does this matter?",
        order=1,
        clusterId="hook_1",
        pedagogicalRole=PedagogicalRole.HOOK,
        contentMode=ContentMode.IMAGE_SUPPORT,
        layoutCandidates=["concept-focus", "concept-with-image"],
        contentBlocks=[ContentBlock(type="headline", text="Why motion matters")],
        visualIntent=VisualIntent(
            purpose="motivate",
            assetType="photo",
            priority="required",
            sourceStrategy="stock",
        ),
        visualMetadata=VisualMetadata(visualType="stock_photo"),
        imageQuery="newton classroom demo",
    )

    result = select_layout_for_slide(slide=slide, theme="blueprint")

    assert result.layout_id == "concept-with-image"
    assert slide.editingHints is not None
    assert slide.editingHints.notes["visual_state"] == "visual_kept"


def test_selector_rejects_image_layout_when_slide_is_not_renderable_as_image():
    slide = Slide(
        title="Hook",
        content="Why does this matter?",
        order=1,
        pedagogicalRole=PedagogicalRole.HOOK,
        contentMode=ContentMode.IMAGE_SUPPORT,
        layoutCandidates=["concept-with-image"],
        contentBlocks=[ContentBlock(type="headline", text="Why motion matters")],
        visualIntent=VisualIntent(
            purpose="motivate",
            assetType="photo",
            priority="required",
            sourceStrategy="stock",
        ),
        imageQuery=None,
    )

    with pytest.raises(LayoutSelectionError):
        select_layout_for_slide(slide=slide, theme="default")


def test_selector_rejects_query_only_image_slide_without_real_visual_asset():
    slide = Slide(
        title="Hook",
        content="Why does this matter?",
        order=1,
        clusterId="hook_1",
        pedagogicalRole=PedagogicalRole.HOOK,
        contentMode=ContentMode.IMAGE_SUPPORT,
        layoutCandidates=["concept-with-image"],
        contentBlocks=[ContentBlock(type="headline", text="Why motion matters")],
        visualIntent=VisualIntent(
            purpose="motivate",
            assetType="photo",
            priority="required",
            sourceStrategy="stock",
        ),
        imageQuery="newton classroom demonstration",
    )

    with pytest.raises(LayoutSelectionError):
        select_layout_for_slide(slide=slide, theme="default")

    assert slide.editingHints is not None
    assert slide.editingHints.notes["visual_state"] == "visual_rejected"


def test_selector_downgrades_weak_image_slide_to_text_layout():
    slide = Slide(
        title="Friction",
        content="Friction opposes motion.",
        order=1,
        clusterId="explain_1",
        pedagogicalRole=PedagogicalRole.EXPLAIN_CORE,
        contentMode=ContentMode.IMAGE_SUPPORT,
        layoutCandidates=["concept-with-image", "concept-focus"],
        contentBlocks=[ContentBlock(type="headline", text="Friction")],
        visualIntent=VisualIntent(
            purpose="explain",
            assetType="photo",
            priority="optional",
            sourceStrategy="stock",
        ),
        imageQuery="friction",
    )

    result = select_layout_for_slide(slide=slide, theme="default")

    assert result.layout_id == "concept-focus"
    assert slide.editingHints is not None
    assert slide.editingHints.notes["visual_state"] == "visual_rejected"


def test_selector_rejects_summary_grid_when_no_takeaway_blocks_exist():
    slide = Slide(
        title="Summary",
        content="Done",
        order=9,
        pedagogicalRole=PedagogicalRole.SUMMARY,
        contentMode=ContentMode.TEXT_ONLY,
        layoutCandidates=["summary-grid"],
        contentBlocks=[ContentBlock(type="headline", text="Summary only")],
    )

    with pytest.raises(LayoutSelectionError):
        select_layout_for_slide(slide=slide, theme="default")


def test_selector_returns_first_valid_candidate_deterministically():
    slide = Slide(
        title="Guided Practice",
        content="Solve the problem.",
        order=4,
        pedagogicalRole=PedagogicalRole.GUIDED_PRACTICE,
        contentMode=ContentMode.QUESTION,
        layoutCandidates=["unknown-layout", "guided-practice", "independent-practice"],
        contentBlocks=[
            ContentBlock(type="headline", text="Try it together"),
            ContentBlock(type="question", text="What force acts here?"),
        ],
    )

    result = select_layout_for_slide(slide=slide, theme="default")

    assert result.layout_id == "guided-practice"


def test_registry_matches_task_3_curated_slice():
    assert set(LAYOUT_REGISTRY["default"]) == {
        "concept-focus",
        "concept-with-image",
        "worked-example",
        "guided-practice",
        "independent-practice",
        "summary-grid",
    }


def test_selector_rejects_worked_example_without_steps_block():
    slide = Slide(
        title="Worked Example",
        content="Model the method.",
        order=3,
        pedagogicalRole=PedagogicalRole.WORKED_EXAMPLE,
        contentMode=ContentMode.COMPARISON,
        layoutCandidates=["worked-example"],
        contentBlocks=[ContentBlock(type="headline", text="Solve step by step")],
    )

    with pytest.raises(LayoutSelectionError):
        select_layout_for_slide(slide=slide, theme="default")


def test_renderer_raises_when_structured_layout_candidates_cannot_be_resolved():
    slide = Slide(
        title="Summary",
        content="Done",
        order=1,
        pedagogicalRole=PedagogicalRole.SUMMARY,
        contentMode=ContentMode.TEXT_ONLY,
        layoutCandidates=["summary-grid"],
        contentBlocks=[ContentBlock(type="headline", text="Missing takeaway")],
    )
    lesson = _build_test_lesson(slide)
    renderer = PPTXRenderer(theme="default")
    prs = _build_test_presentation()

    with pytest.raises(LayoutSelectionError):
        asyncio.run(renderer._create_content_slide(prs, slide, lesson, 1))


def test_renderer_honors_worked_example_layout_selection(monkeypatch):
    slide = Slide(
        title="Worked Example",
        content="Step through the method.",
        order=2,
        pedagogicalRole=PedagogicalRole.WORKED_EXAMPLE,
        contentMode=ContentMode.COMPARISON,
        layoutCandidates=["worked-example"],
        contentBlocks=[
            ContentBlock(type="headline", text="Solve step by step"),
            ContentBlock(type="steps", items=["Set up", "Substitute", "Simplify"]),
        ],
    )
    lesson = _build_test_lesson(slide)
    renderer = PPTXRenderer(theme="default")
    prs = _build_test_presentation()
    calls: list[str] = []

    def fake_worked_example(prs_arg, slide_arg, lesson_arg, index_arg):
        assert prs_arg is prs
        assert slide_arg is slide
        assert lesson_arg is lesson
        assert index_arg == 1
        calls.append("worked-example")

    def fake_concept(*args, **kwargs):
        calls.append("concept")

    monkeypatch.setattr(renderer, "_create_worked_example_slide", fake_worked_example, raising=False)
    monkeypatch.setattr(renderer, "_create_concept_slide", fake_concept)

    asyncio.run(renderer._create_content_slide(prs, slide, lesson, 1))

    assert calls == ["worked-example"]


def test_renderer_image_layout_uses_image_feature_path_when_renderable(monkeypatch):
    slide = Slide(
        title="Hook",
        content="Why does this matter?",
        order=1,
        pedagogicalRole=PedagogicalRole.HOOK,
        contentMode=ContentMode.IMAGE_SUPPORT,
        layoutCandidates=["concept-with-image"],
        contentBlocks=[ContentBlock(type="headline", text="Why motion matters")],
        visualIntent=VisualIntent(
            purpose="motivate",
            assetType="photo",
            priority="required",
            sourceStrategy="stock",
        ),
        visualMetadata=VisualMetadata(visualType="stock_photo"),
        imageQuery="newton motion classroom",
    )
    lesson = _build_test_lesson(slide)
    renderer = PPTXRenderer(theme="default")
    prs = _build_test_presentation()
    calls: list[str] = []

    async def fake_fetch_image(slide_arg, subject_arg):
        assert slide_arg is slide
        assert subject_arg == "Physics"
        return object(), "source"

    def fake_image_feature(prs_arg, slide_arg, lesson_arg, index_arg, image_stream_arg, attribution_arg):
        assert prs_arg is prs
        assert slide_arg is slide
        assert lesson_arg is lesson
        assert index_arg == 1
        assert attribution_arg == "source"
        calls.append("image")

    def fake_concept(*args, **kwargs):
        calls.append("concept")

    monkeypatch.setattr(renderer, "_fetch_image", fake_fetch_image)
    monkeypatch.setattr(renderer, "_create_image_feature_slide", fake_image_feature)
    monkeypatch.setattr(renderer, "_create_concept_slide", fake_concept)

    asyncio.run(renderer._create_content_slide(prs, slide, lesson, 1))

    assert calls == ["image"]


def test_renderer_rejected_visual_slide_uses_text_first_fallback(monkeypatch):
    slide = Slide(
        title="Friction",
        content="Friction opposes motion.",
        order=1,
        clusterId="explain_1",
        pedagogicalRole=PedagogicalRole.EXPLAIN_CORE,
        contentMode=ContentMode.IMAGE_SUPPORT,
        layoutCandidates=["concept-with-image", "concept-focus"],
        contentBlocks=[ContentBlock(type="headline", text="Friction")],
        visualIntent=VisualIntent(
            purpose="explain",
            assetType="photo",
            priority="optional",
            sourceStrategy="stock",
        ),
        imageQuery="friction",
    )
    lesson = _build_test_lesson(slide)
    renderer = PPTXRenderer(theme="default")
    prs = _build_test_presentation()
    calls: list[str] = []

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("image fetch should not run for rejected visual fallback")

    def fake_image_feature(*args, **kwargs):
        calls.append("image")

    def fake_concept(prs_arg, slide_arg, lesson_arg, index_arg):
        assert prs_arg is prs
        assert slide_arg is slide
        assert lesson_arg is lesson
        assert index_arg == 1
        calls.append("concept")

    monkeypatch.setattr(renderer, "_fetch_image", fail_if_called)
    monkeypatch.setattr(renderer, "_create_image_feature_slide", fake_image_feature)
    monkeypatch.setattr(renderer, "_create_concept_slide", fake_concept)

    asyncio.run(renderer._create_content_slide(prs, slide, lesson, 1))

    assert calls == ["concept"]
    assert slide.editingHints is not None
    assert slide.editingHints.notes["visual_state"] == "visual_rejected"


def test_selector_downgrades_structured_image_layout_when_no_real_visual_exists():
    slide = Slide(
        title="Force and Motion",
        content="Describe how force affects motion.",
        order=1,
        pedagogicalRole=PedagogicalRole.EXPLAIN_CORE,
        contentMode=ContentMode.IMAGE_SUPPORT,
        layoutCandidates=["concept-with-image", "concept-focus"],
        contentBlocks=[ContentBlock(type="headline", text="Force and Motion")],
        visualIntent=VisualIntent(
            purpose="explain",
            assetType="photo",
            priority="required",
            sourceStrategy="stock",
        ),
        imageQuery="force and motion classroom demonstration",
    )

    result = select_layout_for_slide(slide=slide, theme="default")

    assert result.layout_id == "concept-focus"
    assert slide.editingHints is not None
    assert slide.editingHints.notes["visual_state"] == "visual_rejected"


def test_renderer_unstructured_image_query_falls_back_without_real_visual(monkeypatch):
    slide = Slide(
        title="Hook",
        content="Why does this matter?",
        order=1,
        slideType=SlideType.INTRODUCTION,
        imageQuery="newton motion classroom demonstration",
    )
    lesson = _build_test_lesson(slide)
    renderer = PPTXRenderer(theme="default")
    prs = _build_test_presentation()
    calls: list[str] = []

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("image fetch should not run for unstructured slides without real visual metadata")

    def fake_image_feature(*args, **kwargs):
        calls.append("image")

    def fake_concept(prs_arg, slide_arg, lesson_arg, index_arg):
        assert prs_arg is prs
        assert slide_arg is slide
        assert lesson_arg is lesson
        assert index_arg == 1
        calls.append("concept")

    monkeypatch.setattr(renderer, "_fetch_image", fail_if_called)
    monkeypatch.setattr(renderer, "_create_image_feature_slide", fake_image_feature)
    monkeypatch.setattr(renderer, "_create_concept_slide", fake_concept)

    asyncio.run(renderer._create_content_slide(prs, slide, lesson, 1))

    assert calls == ["concept"]


def test_renderer_raises_for_non_visual_structured_layout_resolution_errors():
    slide = Slide(
        title="Summary",
        content="Done",
        order=1,
        clusterId="summary_1",
        pedagogicalRole=PedagogicalRole.SUMMARY,
        contentMode=ContentMode.TEXT_ONLY,
        layoutCandidates=["summary-grid"],
        contentBlocks=[ContentBlock(type="headline", text="Missing takeaway")],
        editingHints=EditingHints(notes={"visual_state": "visual_rejected"}),
    )
    lesson = _build_test_lesson(slide)
    renderer = PPTXRenderer(theme="default")
    prs = _build_test_presentation()

    with pytest.raises(LayoutSelectionError):
        asyncio.run(renderer._create_content_slide(prs, slide, lesson, 1))
