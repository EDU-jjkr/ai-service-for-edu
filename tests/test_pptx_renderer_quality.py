import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.lesson_schema import (
    ContentBlock,
    ContentMode,
    PedagogicalRole,
    PracticeMetadata,
    Slide,
)
from app.services.pptx_renderer import (
    THEMES,
    build_concept_render_model,
    build_practice_render_model,
    build_summary_render_model,
    compute_title_font_size,
)


def test_concept_render_model_prefers_structured_blocks_over_raw_text():
    slide = Slide(
        title="Photosynthesis",
        content="Legacy fallback that should not drive the main layout.",
        order=1,
        clusterId="explain_1",
        pedagogicalRole=PedagogicalRole.EXPLAIN_CORE,
        contentMode=ContentMode.TEXT_ONLY,
        instructionalGoal="Explain how plants convert light into stored energy.",
        objective="Students describe the inputs and outputs of photosynthesis.",
        contentBlocks=[
            ContentBlock(type="headline", text="Photosynthesis stores energy"),
            ContentBlock(type="subhead", text="Plants use light, water, and carbon dioxide to make glucose."),
            ContentBlock(type="bullets", items=["Light provides energy", "Water and carbon dioxide are reactants"]),
            ContentBlock(type="callout", text="Glucose is the stored chemical energy plants make."),
        ],
    )

    model = build_concept_render_model(slide)

    assert model.lead == "Photosynthesis stores energy"
    assert model.supporting_points == [
        "Plants use light, water, and carbon dioxide to make glucose.",
        "Light provides energy",
        "Water and carbon dioxide are reactants",
        "Glucose is the stored chemical energy plants make.",
    ]
    assert model.objective == "Explain how plants convert light into stored energy."


def test_practice_render_model_uses_structured_question_hint_and_answer_blocks():
    slide = Slide(
        title="Try It",
        content="Legacy practice content",
        order=3,
        clusterId="practice_1",
        pedagogicalRole=PedagogicalRole.GUIDED_PRACTICE,
        contentMode=ContentMode.QUESTION,
        practiceMetadata=PracticeMetadata(
            difficulty="medium",
            answerMode="hidden_by_default",
            stepCount=3,
            misconception="Students may subtract before dividing.",
        ),
        contentBlocks=[
            ContentBlock(type="headline", text="Solve together"),
            ContentBlock(type="question", text="What is x in 2x + 6 = 18?"),
            ContentBlock(type="hint", text="Undo addition before division."),
            ContentBlock(type="steps", items=["Subtract 6 from both sides", "Divide both sides by 2"]),
            ContentBlock(type="answer", text="x = 6"),
        ],
    )

    model = build_practice_render_model(slide)

    assert model.question == "What is x in 2x + 6 = 18?"
    assert model.work_items == [
        "Undo addition before division.",
        "Subtract 6 from both sides",
        "Divide both sides by 2",
    ]
    assert model.teacher_key == [
        "x = 6",
        "Misconception: Students may subtract before dividing.",
        "Difficulty: medium",
    ]


def test_summary_render_model_prefers_takeaway_blocks():
    slide = Slide(
        title="Summary",
        content="Legacy summary content",
        order=5,
        clusterId="summary_1",
        pedagogicalRole=PedagogicalRole.SUMMARY,
        contentMode=ContentMode.TEXT_ONLY,
        contentBlocks=[
            ContentBlock(type="headline", text="Wrap up"),
            ContentBlock(type="takeaway", text="Energy changes form but is not created or destroyed."),
            ContentBlock(type="takeaway", text="Potential energy depends on position."),
            ContentBlock(type="takeaway", text="Kinetic energy depends on motion."),
        ],
    )

    model = build_summary_render_model(slide)

    assert model.columns == [
        ["Energy changes form but is not created or destroyed."],
        ["Potential energy depends on position."],
        ["Kinetic energy depends on motion."],
    ]


def test_compute_title_font_size_shrinks_for_long_titles():
    short_size = compute_title_font_size("Newton's First Law", compact=False)
    long_size = compute_title_font_size(
        "Newton's First Law and How Unbalanced Forces Change Motion in Real Classroom Demonstrations",
        compact=False,
    )

    assert short_size > long_size
    assert short_size == 32
    assert long_size >= 24


def test_each_theme_has_full_presentation_contract():
    required_keys = {
        "motif",
        "hero_layout",
        "summary_labels",
        "section_divider_style",
        "content_rhythm",
        "image_frame_style",
    }

    for name, theme in THEMES.items():
        assert required_keys.issubset(theme.keys()), name


def test_science_and_math_themes_are_not_structurally_identical():
    assert THEMES["science_nature"]["hero_layout"] != THEMES["mathematics"]["hero_layout"]
    assert THEMES["science_nature"]["content_rhythm"] != THEMES["mathematics"]["content_rhythm"]


def test_theme_catalog_prunes_low_value_basic_variants():
    assert "simple" not in THEMES
    assert "mono" not in THEMES
    assert "storm" not in THEMES
