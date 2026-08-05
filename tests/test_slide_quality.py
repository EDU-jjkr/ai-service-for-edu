import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.lesson_schema import (
    ContentBlock,
    ContentMode,
    DensityLevel,
    EditingHints,
    LearningStructure,
    LessonDeck,
    LessonMetadata,
    PedagogicalRole,
    Slide,
)
from app.services.slide_quality import (
    apply_quality_guards_to_lesson,
    apply_quality_guards_to_slide,
    evaluate_slide_quality,
)


def test_quality_guard_trims_overdense_low_density_support_blocks():
    slide = Slide(
        title="States of Matter",
        content="Legacy content",
        order=1,
        density=DensityLevel.LOW,
        pedagogicalRole=PedagogicalRole.EXPLAIN_CORE,
        contentMode=ContentMode.TEXT_ONLY,
        contentBlocks=[
            ContentBlock(type="headline", text="States of Matter"),
            ContentBlock(type="bullets", items=[
                "Solids keep their shape",
                "Liquids flow but keep volume",
                "Gases expand to fill space",
                "Particles move faster when heated",
                "Matter changes state with energy",
            ]),
        ],
    )

    guarded = apply_quality_guards_to_slide(slide)

    assert guarded.contentBlocks[1].items == [
        "Solids keep their shape",
        "Liquids flow but keep volume",
        "Gases expand to fill space",
    ]
    assert guarded.editingHints is not None
    assert guarded.editingHints.notes["quality_warnings"] == ["over_dense_support"]


def test_quality_guard_flags_generic_language_for_regeneration():
    slide = Slide(
        title="Introduction",
        content="In this lesson students learn about an important topic and understand the concept.",
        order=1,
        pedagogicalRole=PedagogicalRole.EXPLAIN_CORE,
        contentMode=ContentMode.TEXT_ONLY,
        contentBlocks=[ContentBlock(type="headline", text="Learn about this important topic")],
    )

    result = evaluate_slide_quality(slide)

    assert "generic_language" in result.warnings
    assert result.requires_regeneration is True


def test_quality_guard_flags_question_slides_missing_question_blocks():
    slide = Slide(
        title="Practice",
        content="Try solving this equation.",
        order=2,
        pedagogicalRole=PedagogicalRole.GUIDED_PRACTICE,
        contentMode=ContentMode.QUESTION,
        contentBlocks=[ContentBlock(type="headline", text="Try it")],
    )

    guarded = apply_quality_guards_to_slide(slide)

    assert guarded.editingHints is not None
    assert "missing_question_block" in guarded.editingHints.notes["quality_warnings"]
    assert guarded.editingHints.notes["requires_regeneration"] is True


def test_quality_guard_applies_across_lesson_deck():
    lesson = LessonDeck(
        meta=LessonMetadata(topic="Energy", subject="Science", grade="8", theme="default"),
        structure=LearningStructure(
            learning_objectives=[],
            vocabulary=[],
            prerequisites=[],
            bloom_progression=[],
        ),
        slides=[
            Slide(
                title="Summary",
                content="Legacy summary",
                order=1,
                pedagogicalRole=PedagogicalRole.SUMMARY,
                contentMode=ContentMode.TEXT_ONLY,
                editingHints=EditingHints(notes={"cluster_status": "approved"}),
                contentBlocks=[
                    ContentBlock(type="headline", text="Wrap up"),
                    ContentBlock(type="takeaway", items=["Energy changes form", "Potential energy depends on position"]),
                ],
            )
        ],
    )

    guarded = apply_quality_guards_to_lesson(lesson)

    assert guarded.slides[0].editingHints is not None
    assert guarded.slides[0].editingHints.notes["cluster_status"] == "approved"
    assert "quality_score" in guarded.slides[0].editingHints.notes
