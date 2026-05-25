"""
PowerPoint theme seed generator.

These files are not used as fragile master-slide dependencies anymore. They are
seeded, usable sample decks for each available theme, so product demos and
template previews look polished instead of blank.
"""

from pathlib import Path
import asyncio
import logging

from app.models.lesson_schema import (
    BloomLevel,
    LearningObjective,
    LearningStructure,
    LessonDeck,
    LessonMetadata,
    Slide,
    SlideType,
)
from app.services.pptx_renderer import PPTXRenderer, THEMES

logger = logging.getLogger(__name__)


def _sample_deck(theme: str) -> LessonDeck:
    theme_label = THEMES.get(theme, THEMES["default"])["name"]
    return LessonDeck(
        meta=LessonMetadata(
            topic=f"{theme_label} Template",
            subject="Template Preview",
            grade="10",
            standards=[],
            theme=theme,
        ),
        structure=LearningStructure(
            learning_objectives=[
                LearningObjective(
                    objective="Preview the title, concept, practice, and summary layouts.",
                    bloom_level=BloomLevel.UNDERSTAND,
                )
            ],
            vocabulary=[],
            prerequisites=[],
            bloom_progression=[
                BloomLevel.REMEMBER,
                BloomLevel.UNDERSTAND,
                BloomLevel.APPLY,
                BloomLevel.CREATE,
            ],
        ),
        slides=[
            Slide(
                title="Start With A Strong Hook",
                content=(
                    "Open with one curiosity question\n"
                    "Name the core idea in simple language\n"
                    "Show why it matters beyond the textbook\n"
                    "Preview what students will be able to do"
                ),
                order=1,
                slideType=SlideType.INTRODUCTION,
                bloom_level=BloomLevel.REMEMBER,
                objective="Introduce the topic with context and purpose.",
                imageQuery="teacher demonstrating science experiment",
                speakerNotes="Use this slide to set purpose and activate prior knowledge.",
            ),
            Slide(
                title="Make The Core Idea Visible",
                content=(
                    "Teach one key idea per slide\n"
                    "Pair the idea with an example or analogy\n"
                    "Call out one misconception early\n"
                    "End with a quick check question"
                ),
                order=2,
                slideType=SlideType.CONCEPT,
                bloom_level=BloomLevel.UNDERSTAND,
                objective="Explain a concept with a visual anchor.",
                speakerNotes="Keep the slide concise and put the extra explanation here.",
            ),
            Slide(
                title="Practice With Feedback",
                content=(
                    "Question: Which option best explains the idea?\n"
                    "A) A surface detail only\n"
                    "B) A cause-and-effect relationship\n"
                    "C) An unrelated example\n"
                    "D) A memorized definition\n"
                    "Answer: B\n"
                    "Explanation: Students should identify the relationship, not just recall words."
                ),
                order=3,
                slideType=SlideType.ACTIVITY,
                bloom_level=BloomLevel.APPLY,
                objective="Apply the concept in a short check.",
                speakerNotes="Let students answer first, then reveal the teacher key.",
            ),
            Slide(
                title="Close With Transfer",
                content=(
                    "Students can define the key idea\n"
                    "Students can explain it with an example\n"
                    "Students can avoid the common misconception\n"
                    "Students can apply it to a new scenario"
                ),
                order=4,
                slideType=SlideType.SUMMARY,
                bloom_level=BloomLevel.CREATE,
                objective="Summarize learning and transfer it forward.",
                speakerNotes="Use this as an exit-ticket prompt.",
            ),
        ],
    )


async def create_theme_template(theme: str) -> str:
    templates_dir = Path(__file__).parent.parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    output_path = templates_dir / f"{theme}.pptx"
    pptx = await PPTXRenderer(theme=theme).render_lesson_deck(_sample_deck(theme))
    output_path.write_bytes(pptx.getvalue())
    logger.info("Template created: %s", output_path)
    return str(output_path)


async def create_all_templates() -> list[str]:
    created = []
    for theme in THEMES:
        created.append(await create_theme_template(theme))
    return created


def initialize_templates(force: bool = True) -> list[str]:
    """
    Seed all templates.

    force=True refreshes old placeholder files so existing installations get the
    upgraded design immediately.
    """
    templates_dir = Path(__file__).parent.parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    if force:
        return asyncio.run(create_all_templates())

    missing = [theme for theme in THEMES if not (templates_dir / f"{theme}.pptx").exists()]
    created = []
    for theme in missing:
        created.append(asyncio.run(create_theme_template(theme)))
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    paths = initialize_templates(force=True)
    print(f"Templates initialized: {len(paths)}")
    print(f"Location: {Path(__file__).parent.parent / 'templates'}")
