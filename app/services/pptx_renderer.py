"""
Market-ready PPTX renderer for generated lesson decks.

The previous renderer depended on placeholder layouts inside seeded template
files. In practice those templates were mostly blank, so exported decks looked
plain and image/chart placement was fragile. This renderer owns the visual
system directly: typography, colors, slide composition, images, charts, and
speaker notes are all placed programmatically.
"""

from io import BytesIO
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import logging
import re
import requests

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from app.models.lesson_schema import ContentMode, LessonDeck, Slide, SlideType
from app.services.stock_photo_service import StockPhotoService
from app.services.image_processor import ImageProcessor
from app.services.layout_selector import (
    LayoutSelectionError,
    VISUAL_STATE_REJECTED,
    get_visual_outcome,
    select_layout_for_slide,
)

logger = logging.getLogger(__name__)


SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


THEMES: Dict[str, Dict[str, Any]] = {
    "default": {
        "name": "Editorial",
        "bg": (248, 250, 252),
        "ink": (17, 24, 39),
        "muted": (82, 94, 113),
        "accent": (20, 184, 166),
        "accent2": (244, 63, 94),
        "panel": (255, 255, 255),
        "soft": (226, 232, 240),
        "motif": "editorial",
        "hero_layout": "split-right",
        "summary_labels": ("Remember", "Connect", "Apply Next"),
        "section_divider_style": "editorial_rule",
        "content_rhythm": "balanced",
        "image_frame_style": "editorial_window",
    },
    "science_nature": {
        "name": "Field Lab",
        "bg": (241, 248, 245),
        "ink": (16, 43, 38),
        "muted": (65, 91, 84),
        "accent": (16, 185, 129),
        "accent2": (14, 165, 233),
        "panel": (255, 255, 255),
        "soft": (209, 250, 229),
        "motif": "field",
        "hero_layout": "frame",
        "summary_labels": ("Observe", "Explain", "Apply"),
        "section_divider_style": "field_notebook",
        "content_rhythm": "observational",
        "image_frame_style": "soft_lab_card",
    },
    "mathematics": {
        "name": "Graph Paper",
        "bg": (246, 248, 251),
        "ink": (15, 23, 42),
        "muted": (71, 85, 105),
        "accent": (37, 99, 235),
        "accent2": (217, 119, 6),
        "panel": (255, 255, 255),
        "soft": (219, 234, 254),
        "motif": "graph",
        "hero_layout": "band",
        "summary_labels": ("Recall", "Model", "Solve"),
        "section_divider_style": "grid_band",
        "content_rhythm": "problem_solution",
        "image_frame_style": "graph_window",
    },
    "mint": {
        "name": "Mint Lab",
        "bg": (240, 253, 250),
        "ink": (19, 47, 46),
        "muted": (71, 85, 105),
        "accent": (45, 212, 191),
        "accent2": (99, 102, 241),
        "panel": (255, 255, 255),
        "soft": (204, 251, 241),
        "motif": "field",
        "hero_layout": "spotlight",
        "summary_labels": ("Notice", "Clarify", "Practice"),
        "section_divider_style": "field_notebook",
        "content_rhythm": "guided_lab",
        "image_frame_style": "soft_lab_card",
    },
    "blueprint": {
        "name": "Blueprint",
        "bg": (239, 246, 255),
        "ink": (15, 23, 42),
        "muted": (51, 65, 85),
        "accent": (37, 99, 235),
        "accent2": (14, 165, 233),
        "panel": (255, 255, 255),
        "soft": (191, 219, 254),
        "motif": "blueprint",
        "hero_layout": "split-right",
        "summary_labels": ("Recall", "Engineer", "Try Next"),
        "section_divider_style": "blueprint_ticks",
        "content_rhythm": "sequenced_build",
        "image_frame_style": "blueprint_plate",
    },
    "folio": {
        "name": "Folio",
        "bg": (255, 247, 247),
        "ink": (63, 22, 44),
        "muted": (100, 67, 82),
        "accent": (225, 29, 72),
        "accent2": (14, 165, 233),
        "panel": (255, 255, 255),
        "soft": (255, 228, 230),
        "motif": "folio",
        "hero_layout": "frame",
        "summary_labels": ("Remember", "Discuss", "Respond"),
        "section_divider_style": "folio_margin",
        "content_rhythm": "seminar",
        "image_frame_style": "folio_polaroid",
    },
    "deep": {
        "name": "Deep Focus",
        "bg": (15, 23, 42),
        "ink": (248, 250, 252),
        "muted": (203, 213, 225),
        "accent": (45, 212, 191),
        "accent2": (251, 191, 36),
        "panel": (30, 41, 59),
        "soft": (51, 65, 85),
        "motif": "deep",
        "hero_layout": "spotlight",
        "summary_labels": ("Anchor", "Connect", "Push Further"),
        "section_divider_style": "spotlight_beam",
        "content_rhythm": "cinematic",
        "image_frame_style": "dark_stage",
    },
    "dark": {
        "name": "Night Class",
        "bg": (24, 24, 27),
        "ink": (250, 250, 250),
        "muted": (212, 212, 216),
        "accent": (52, 211, 153),
        "accent2": (96, 165, 250),
        "panel": (39, 39, 42),
        "soft": (63, 63, 70),
        "motif": "deep",
        "hero_layout": "split-right",
        "summary_labels": ("Remember", "Reflect", "Next Move"),
        "section_divider_style": "night_rule",
        "content_rhythm": "reflection",
        "image_frame_style": "dark_stage",
    },
    "rust": {
        "name": "Archive",
        "bg": (255, 251, 245),
        "ink": (49, 32, 25),
        "muted": (92, 64, 51),
        "accent": (194, 65, 12),
        "accent2": (13, 148, 136),
        "panel": (255, 255, 255),
        "soft": (254, 215, 170),
        "motif": "archive",
        "hero_layout": "frame",
        "summary_labels": ("Key Fact", "Context", "Discuss"),
        "section_divider_style": "archive_stamp",
        "content_rhythm": "narrative",
        "image_frame_style": "archive_matte",
    },
}


def rgb(value: Tuple[int, int, int]) -> RGBColor:
    return RGBColor(*value)


def clean_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("**", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_content(content: str) -> List[str]:
    lines: List[str] = []
    for raw in clean_text(content).splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[\-*•]\s*", "", line)
        line = re.sub(r"^\d+[\.)]\s*", "", line)
        if line:
            lines.append(line)
    return lines


def shorten(text: str, limit: int = 170) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{cut}..."


@dataclass(frozen=True)
class ConceptRenderModel:
    lead: str
    supporting_points: List[str]
    objective: str


@dataclass(frozen=True)
class PracticeRenderModel:
    question: str
    work_items: List[str]
    teacher_key: List[str]


@dataclass(frozen=True)
class SummaryRenderModel:
    columns: List[List[str]]


def _first_block_text(slide: Slide, block_type: str) -> Optional[str]:
    for block in slide.contentBlocks:
        if block.type == block_type and block.text:
            return clean_text(block.text)
    return None


def _block_items(slide: Slide, block_type: str) -> List[str]:
    items: List[str] = []
    for block in slide.contentBlocks:
        if block.type != block_type:
            continue
        if block.text:
            items.append(clean_text(block.text))
        items.extend(clean_text(item) for item in block.items if clean_text(item))
    return items


def _structured_points(slide: Slide, block_types: Tuple[str, ...]) -> List[str]:
    points: List[str] = []
    for block_type in block_types:
        points.extend(_block_items(slide, block_type))
    return points


def compute_title_font_size(title: str, compact: bool) -> int:
    length = len(clean_text(title))
    if compact:
        if length > 95:
            return 22
        if length > 65:
            return 24
        if length > 42:
            return 26
        return 28

    if length > 95:
        return 24
    if length > 65:
        return 27
    if length > 42:
        return 30
    return 32


def build_concept_render_model(slide: Slide) -> ConceptRenderModel:
    legacy_lines = split_content(slide.content)
    lead = (
        _first_block_text(slide, "headline")
        or _first_block_text(slide, "subhead")
        or (legacy_lines[0] if legacy_lines else slide.objective or slide.title)
    )
    supporting_points = _structured_points(slide, ("subhead", "bullets", "callout", "example", "hint"))
    if lead in supporting_points:
        supporting_points = [point for point in supporting_points if point != lead]
    if not supporting_points:
        supporting_points = legacy_lines[1:7]

    objective = clean_text(slide.instructionalGoal or slide.objective or "Use the key idea in a classroom example.")
    return ConceptRenderModel(
        lead=clean_text(lead),
        supporting_points=supporting_points[:6],
        objective=objective,
    )


def build_practice_render_model(slide: Slide) -> PracticeRenderModel:
    question = (
        _first_block_text(slide, "question")
        or _first_block_text(slide, "headline")
        or next(iter(split_content(slide.content)), slide.title)
    )
    work_items = _structured_points(slide, ("hint", "steps", "bullets"))
    if not work_items:
        lines = split_content(slide.content)
        work_items = lines[1:5] if len(lines) > 1 else ["Think first", "Show your method", "Compare with a partner"]

    teacher_key = _structured_points(slide, ("answer", "solution", "explanation"))
    misconception = slide.practiceMetadata.misconception if slide.practiceMetadata else None
    difficulty = slide.practiceMetadata.difficulty if slide.practiceMetadata else None
    if misconception:
        teacher_key.append(f"Misconception: {clean_text(misconception)}")
    if difficulty:
        teacher_key.append(f"Difficulty: {clean_text(difficulty)}")
    if not teacher_key:
        teacher_key = ["Discuss multiple solution paths before revealing the answer."]

    return PracticeRenderModel(
        question=clean_text(question),
        work_items=work_items[:4],
        teacher_key=teacher_key[:4],
    )


def build_summary_render_model(slide: Slide) -> SummaryRenderModel:
    takeaways = _block_items(slide, "takeaway")
    if not takeaways:
        takeaways = split_content(slide.content)[:9]
    columns = [takeaways[0::3], takeaways[1::3], takeaways[2::3]]
    return SummaryRenderModel(columns=columns)


class PPTXRenderer:
    def __init__(self, theme: str = "default"):
        self.theme_name = theme if theme in THEMES else "default"
        self.theme = THEMES[self.theme_name]
        self.stock_photo_service = StockPhotoService()
        self.image_processor = ImageProcessor()
        logger.info("PPTXRenderer initialized with theme: %s", self.theme_name)

    async def render_lesson_deck(self, lesson: LessonDeck) -> BytesIO:
        logger.info("Rendering lesson: %s (%s slides)", lesson.meta.topic, len(lesson.slides))

        prs = Presentation()
        prs.slide_width = SLIDE_W
        prs.slide_height = SLIDE_H

        self._create_title_slide(prs, lesson)
        for index, slide_data in enumerate(sorted(lesson.slides, key=lambda s: s.order), start=1):
            await self._create_content_slide(prs, slide_data, lesson, index)
        self._create_closing_slide(prs, lesson)

        output = BytesIO()
        prs.save(output)
        output.seek(0)
        logger.info("PPTX rendered successfully")
        return output

    def _blank(self, prs: Presentation):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._paint_background(slide)
        self._apply_theme_motif(slide, context="content")
        return slide

    def _paint_background(self, slide) -> None:
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(self.theme["bg"])

    def _apply_theme_motif(self, slide, context: str) -> None:
        motif = self.theme.get("motif", "editorial")
        if motif == "blueprint":
            for x in (Inches(0.45), Inches(12.3)):
                self._add_rect(slide, x, Inches(0.45), Inches(0.06), Inches(6.55), self.theme["accent"], radius=False, transparency=78)
            for y in (Inches(0.55), Inches(6.8)):
                self._add_rect(slide, Inches(0.45), y, Inches(12.4), Inches(0.04), self.theme["accent2"], radius=False, transparency=84)
        elif motif == "graph":
            for x in (Inches(0.75), Inches(2.2), Inches(3.65), Inches(5.1), Inches(6.55), Inches(8.0), Inches(9.45), Inches(10.9)):
                self._add_rect(slide, x, Inches(0.48), Inches(0.02), Inches(6.45), self.theme["soft"], radius=False, transparency=84)
            for y in (Inches(1.15), Inches(2.15), Inches(3.15), Inches(4.15), Inches(5.15), Inches(6.15)):
                self._add_rect(slide, Inches(0.55), y, Inches(12.1), Inches(0.02), self.theme["soft"], radius=False, transparency=84)
        elif motif == "field":
            self._add_rect(slide, Inches(0.42), Inches(0.42), Inches(1.85), Inches(0.12), self.theme["accent"], radius=False, transparency=58)
            self._add_rect(slide, Inches(11.0), Inches(6.86), Inches(1.85), Inches(0.12), self.theme["accent2"], radius=False, transparency=62)
        elif motif == "folio":
            self._add_rect(slide, Inches(0.42), Inches(0.42), Inches(0.08), Inches(6.65), self.theme["accent"], radius=False, transparency=74)
            self._add_rect(slide, Inches(12.68), Inches(0.42), Inches(0.08), Inches(6.65), self.theme["accent2"], radius=False, transparency=82)
        elif motif == "archive":
            self._add_rect(slide, Inches(0.42), Inches(0.46), Inches(12.4), Inches(0.08), self.theme["accent"], radius=False, transparency=78)
            self._add_rect(slide, Inches(0.42), Inches(6.9), Inches(12.4), Inches(0.08), self.theme["accent2"], radius=False, transparency=86)
        elif motif == "deep":
            self._add_rect(slide, Inches(0.5), Inches(6.72), Inches(4.0), Inches(0.12), self.theme["accent"], radius=False, transparency=52)
            self._add_rect(slide, Inches(8.4), Inches(0.5), Inches(0.12), Inches(2.4), self.theme["accent2"], radius=False, transparency=66)
        elif motif == "storm":
            self._add_rect(slide, Inches(0.5), Inches(0.5), Inches(12.2), Inches(0.05), self.theme["muted"], radius=False, transparency=84)
            self._add_rect(slide, Inches(0.5), Inches(6.88), Inches(12.2), Inches(0.05), self.theme["muted"], radius=False, transparency=88)
        elif motif == "mono":
            self._add_rect(slide, Inches(0.5), Inches(0.5), Inches(2.25), Inches(0.08), self.theme["ink"], radius=False, transparency=78)
            self._add_rect(slide, Inches(10.55), Inches(6.86), Inches(2.2), Inches(0.08), self.theme["accent2"], radius=False, transparency=70)
        elif motif == "studio":
            self._add_rect(slide, Inches(0.5), Inches(0.5), Inches(0.12), Inches(1.4), self.theme["accent2"], radius=False, transparency=76)
            self._add_rect(slide, Inches(12.55), Inches(5.6), Inches(0.12), Inches(1.35), self.theme["accent"], radius=False, transparency=70)
        elif motif == "editorial":
            self._add_rect(slide, Inches(11.2), Inches(0.45), Inches(1.4), Inches(0.08), self.theme["accent"], radius=False, transparency=74)
            self._add_rect(slide, Inches(0.55), Inches(6.82), Inches(1.8), Inches(0.08), self.theme["accent2"], radius=False, transparency=80)

    def _add_rect(self, slide, left, top, width, height, fill, radius=True, line=None, transparency=0):
        shape = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE if radius else MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            left,
            top,
            width,
            height,
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill)
        shape.fill.transparency = transparency
        if line:
            shape.line.color.rgb = rgb(line)
            shape.line.width = Pt(1)
        else:
            shape.line.fill.background()
        return shape

    def _add_text(
        self,
        slide,
        text: str,
        left,
        top,
        width,
        height,
        font_size=24,
        bold=False,
        color=None,
        align=PP_ALIGN.LEFT,
        valign=MSO_ANCHOR.TOP,
        font="Aptos",
    ):
        box = slide.shapes.add_textbox(left, top, width, height)
        frame = box.text_frame
        frame.clear()
        frame.word_wrap = True
        frame.margin_left = Inches(0.02)
        frame.margin_right = Inches(0.02)
        frame.margin_top = Inches(0.02)
        frame.margin_bottom = Inches(0.02)
        frame.vertical_anchor = valign
        p = frame.paragraphs[0]
        p.text = clean_text(text)
        p.alignment = align
        p.font.name = font
        p.font.size = Pt(font_size)
        p.font.bold = bold
        p.font.color.rgb = rgb(color or self.theme["ink"])
        return box

    def _add_tag(self, slide, text: str, left, top, width=None, fill=None):
        width = width or Inches(max(1.1, min(2.8, len(text) * 0.09)))
        pill = self._add_rect(slide, left, top, width, Inches(0.34), fill or self.theme["accent"], radius=True)
        self._add_text(
            slide,
            text.upper(),
            left + Inches(0.1),
            top + Inches(0.055),
            width - Inches(0.2),
            Inches(0.18),
            font_size=8,
            bold=True,
            color=(255, 255, 255),
            align=PP_ALIGN.CENTER,
        )
        return pill

    def _create_title_slide(self, prs: Presentation, lesson: LessonDeck):
        slide = self._blank(prs)
        hero_layout = self.theme.get("hero_layout", "split-right")
        self._add_rect(slide, Inches(0), Inches(0), SLIDE_W, SLIDE_H, self.theme["bg"], radius=False)
        if hero_layout == "split-right":
            self._add_rect(slide, Inches(7.4), Inches(0), Inches(5.93), SLIDE_H, self.theme["accent"], radius=False)
            self._add_rect(slide, Inches(8.1), Inches(0.72), Inches(4.55), Inches(6.05), self.theme["panel"], radius=True, transparency=6)
        elif hero_layout == "frame":
            self._add_rect(slide, Inches(0.62), Inches(0.62), Inches(12.0), Inches(6.25), self.theme["panel"], radius=True, line=self.theme["soft"])
            self._add_rect(slide, Inches(0.62), Inches(0.62), Inches(12.0), Inches(0.28), self.theme["accent"], radius=False, transparency=20)
        elif hero_layout == "band":
            self._add_rect(slide, Inches(0), Inches(0.58), SLIDE_W, Inches(0.48), self.theme["accent"], radius=False, transparency=18)
            self._add_rect(slide, Inches(0.9), Inches(1.28), Inches(11.45), Inches(5.55), self.theme["panel"], radius=True, line=self.theme["soft"])
        elif hero_layout == "spotlight":
            self._add_rect(slide, Inches(0.78), Inches(0.74), Inches(5.45), Inches(5.95), self.theme["accent"], radius=True, transparency=14)
            self._add_rect(slide, Inches(6.4), Inches(0.92), Inches(5.88), Inches(5.6), self.theme["panel"], radius=True, line=self.theme["soft"])

        topic = lesson.meta.topic
        subtitle = f"Grade {lesson.meta.grade} | {lesson.meta.subject}"
        self._add_tag(slide, self.theme["name"], Inches(0.82), Inches(0.72))
        self._add_text(slide, topic, Inches(0.82), Inches(1.45), Inches(6.2), Inches(1.55), font_size=42, bold=True)
        self._add_text(slide, subtitle, Inches(0.86), Inches(3.08), Inches(5.6), Inches(0.36), font_size=15, color=self.theme["muted"])
        self._add_text(
            slide,
            "A classroom-ready deck with guided explanation, practice, and checks for understanding.",
            Inches(0.86),
            Inches(3.75),
            Inches(5.9),
            Inches(0.72),
            font_size=18,
            color=self.theme["muted"],
        )

        objectives = [obj.objective for obj in lesson.structure.learning_objectives[:3]]
        if not objectives:
            objectives = [s.objective or s.title for s in lesson.slides[:3]]
        self._add_section_list(slide, "Learning Targets", objectives[:3], Inches(8.52), Inches(1.35), Inches(3.75), Inches(3.2))
        self._add_text(slide, f"{len(lesson.slides)} lesson slides", Inches(8.55), Inches(5.55), Inches(3.3), Inches(0.32), 16, True, self.theme["ink"])
        self._add_text(slide, "Built for teaching, discussion, and revision.", Inches(8.55), Inches(5.98), Inches(3.35), Inches(0.36), 12, False, self.theme["muted"])

    async def _create_content_slide(self, prs: Presentation, slide_data: Slide, lesson: LessonDeck, index: int):
        if await self._render_structured_layout(prs, slide_data, lesson, index):
            return

        visual_outcome = get_visual_outcome(slide_data)
        has_real_visual = bool(slide_data.visualMetadata and slide_data.visualMetadata.visualType)
        slide_type = slide_data.slideType
        visual = self._extract_chart_config(slide_data)
        if visual:
            self._create_chart_slide(prs, slide_data, lesson, index, visual)
        elif (
            slide_type == SlideType.INTRODUCTION
            and slide_data.imageQuery
            and visual_outcome != VISUAL_STATE_REJECTED
            and has_real_visual
        ):
            image_stream, attribution = await self._fetch_image(slide_data, lesson.meta.subject)
            if image_stream:
                self._create_image_feature_slide(prs, slide_data, lesson, index, image_stream, attribution)
            else:
                self._create_concept_slide(prs, slide_data, lesson, index)
        elif slide_type in [SlideType.ACTIVITY, SlideType.ASSESSMENT]:
            self._create_practice_slide(prs, slide_data, lesson, index)
        elif slide_type == SlideType.SUMMARY:
            self._create_summary_slide(prs, slide_data, lesson, index)
        elif (
            slide_data.imageQuery
            and visual_outcome != VISUAL_STATE_REJECTED
            and has_real_visual
        ):
            image_stream, attribution = await self._fetch_image(slide_data, lesson.meta.subject)
            if image_stream:
                self._create_image_feature_slide(prs, slide_data, lesson, index, image_stream, attribution)
            else:
                self._create_concept_slide(prs, slide_data, lesson, index)
        else:
            self._create_concept_slide(prs, slide_data, lesson, index)

    async def _render_structured_layout(self, prs: Presentation, slide_data: Slide, lesson: LessonDeck, index: int) -> bool:
        if not slide_data.layoutCandidates:
            return False

        try:
            selected_layout = select_layout_for_slide(slide=slide_data, theme=lesson.meta.theme)
        except LayoutSelectionError:
            if (
                get_visual_outcome(slide_data) == VISUAL_STATE_REJECTED
                and slide_data.contentMode == ContentMode.IMAGE_SUPPORT
            ):
                self._create_concept_slide(prs, slide_data, lesson, index)
                return True
            raise
        layout_id = selected_layout.layout_id
        visual_outcome = get_visual_outcome(slide_data)
        has_real_visual = bool(slide_data.visualMetadata and slide_data.visualMetadata.visualType)

        if layout_id in {"guided-practice", "independent-practice"}:
            self._create_practice_slide(prs, slide_data, lesson, index)
            return True

        if layout_id == "summary-grid":
            self._create_summary_slide(prs, slide_data, lesson, index)
            return True

        if layout_id == "worked-example":
            self._create_worked_example_slide(prs, slide_data, lesson, index)
            return True

        if layout_id == "concept-with-image":
            if visual_outcome == VISUAL_STATE_REJECTED or not has_real_visual:
                self._create_concept_slide(prs, slide_data, lesson, index)
                return True
            image_stream, attribution = await self._fetch_image(slide_data, lesson.meta.subject)
            if image_stream:
                self._create_image_feature_slide(prs, slide_data, lesson, index, image_stream, attribution)
            else:
                self._create_concept_slide(prs, slide_data, lesson, index)
            return True

        self._create_concept_slide(prs, slide_data, lesson, index)
        return True

    def _slide_header(self, slide, slide_data: Slide, lesson: LessonDeck, index: int, compact=False):
        top = Inches(0.38)
        self._add_tag(slide, slide_data.slideType.value, Inches(0.62), top, fill=self.theme["accent"])
        self._add_text(slide, f"{index:02d}", Inches(11.9), top, Inches(0.55), Inches(0.25), 10, True, self.theme["muted"], PP_ALIGN.RIGHT)
        title_size = compute_title_font_size(slide_data.title, compact=compact)
        self._add_text(slide, slide_data.title, Inches(0.62), Inches(0.86), Inches(8.85), Inches(0.82), title_size, True)
        if slide_data.bloom_level:
            self._add_tag(slide, slide_data.bloom_level.value, Inches(9.85), Inches(0.84), Inches(1.65), fill=self.theme["accent2"])

    def _add_section_list(self, slide, title: str, items: List[str], left, top, width, height, max_items=5):
        self._add_text(slide, title, left, top, width, Inches(0.32), 14, True, self.theme["ink"])
        y = top + Inches(0.55)
        for item in items[:max_items]:
            dot = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.OVAL, left, y + Inches(0.06), Inches(0.13), Inches(0.13))
            dot.fill.solid()
            dot.fill.fore_color.rgb = rgb(self.theme["accent"])
            dot.line.fill.background()
            self._add_text(slide, shorten(item, 120), left + Inches(0.28), y, width - Inches(0.3), Inches(0.42), 11.5, False, self.theme["muted"])
            y += Inches(0.5)

    def _add_theme_divider(self, slide, left, top, width) -> None:
        divider_style = self.theme.get("section_divider_style", "editorial_rule")
        if divider_style == "field_notebook":
            self._add_rect(slide, left, top, width, Inches(0.12), self.theme["accent"], radius=False, transparency=30)
            self._add_rect(slide, left + Inches(0.18), top + Inches(0.18), width - Inches(0.36), Inches(0.02), self.theme["accent2"], radius=False, transparency=60)
        elif divider_style == "grid_band":
            self._add_rect(slide, left, top, width, Inches(0.08), self.theme["accent"], radius=False, transparency=18)
            for offset in (Inches(0.65), Inches(1.3), Inches(1.95)):
                if offset < width:
                    self._add_rect(slide, left + offset, top - Inches(0.06), Inches(0.02), Inches(0.2), self.theme["accent2"], radius=False, transparency=28)
        elif divider_style == "blueprint_ticks":
            self._add_rect(slide, left, top, width, Inches(0.08), self.theme["accent"], radius=False, transparency=22)
            for offset in (Inches(0.48), Inches(1.18), Inches(1.88), Inches(2.58)):
                if offset < width:
                    self._add_rect(slide, left + offset, top - Inches(0.08), Inches(0.02), Inches(0.24), self.theme["accent2"], radius=False, transparency=35)
        elif divider_style == "folio_margin":
            self._add_rect(slide, left, top, width, Inches(0.06), self.theme["accent2"], radius=False, transparency=35)
            self._add_rect(slide, left, top + Inches(0.14), Inches(0.9), Inches(0.04), self.theme["accent"], radius=False, transparency=18)
        elif divider_style == "spotlight_beam":
            self._add_rect(slide, left, top, width, Inches(0.1), self.theme["accent"], radius=False, transparency=12)
            self._add_rect(slide, left + Inches(0.55), top + Inches(0.16), Inches(1.45), Inches(0.04), self.theme["accent2"], radius=False, transparency=24)
        elif divider_style == "night_rule":
            self._add_rect(slide, left, top, width, Inches(0.06), self.theme["soft"], radius=False, transparency=10)
            self._add_rect(slide, left, top + Inches(0.14), Inches(1.1), Inches(0.04), self.theme["accent"], radius=False, transparency=8)
        elif divider_style == "archive_stamp":
            self._add_rect(slide, left, top, width, Inches(0.08), self.theme["accent"], radius=False, transparency=26)
            self._add_rect(slide, left + width - Inches(1.1), top - Inches(0.04), Inches(1.1), Inches(0.16), self.theme["accent2"], radius=False, transparency=48)
        else:
            self._add_rect(slide, left, top, width, Inches(0.08), self.theme["accent"], radius=False, transparency=24)

    def _content_section_title(self) -> str:
        rhythm = self.theme.get("content_rhythm", "balanced")
        if rhythm == "problem_solution":
            return "Solve the pattern"
        if rhythm in {"observational", "guided_lab"}:
            return "What students should observe"
        if rhythm == "seminar":
            return "Points to discuss"
        if rhythm == "sequenced_build":
            return "What to build next"
        if rhythm == "reflection":
            return "What to reflect on"
        if rhythm == "narrative":
            return "What to carry forward"
        if rhythm == "cinematic":
            return "What to spotlight"
        return "What students should notice"

    def _practice_section_title(self) -> str:
        rhythm = self.theme.get("content_rhythm", "balanced")
        if rhythm == "problem_solution":
            return "Solve"
        if rhythm in {"observational", "guided_lab"}:
            return "Lab moves"
        if rhythm == "seminar":
            return "Discussion moves"
        if rhythm == "reflection":
            return "Reflection prompts"
        return "Work Time"

    def _style_image_frame(self, slide, left, top, width, height) -> None:
        frame_style = self.theme.get("image_frame_style", "editorial_window")
        if frame_style == "soft_lab_card":
            self._add_rect(slide, left - Inches(0.18), top - Inches(0.18), width + Inches(0.36), height + Inches(0.36), self.theme["panel"], radius=True, line=self.theme["soft"])
            self._add_rect(slide, left - Inches(0.06), top - Inches(0.06), width + Inches(0.12), height + Inches(0.12), self.theme["soft"], radius=True, transparency=50)
        elif frame_style == "graph_window":
            self._add_rect(slide, left - Inches(0.16), top - Inches(0.16), width + Inches(0.32), height + Inches(0.32), self.theme["panel"], radius=False, line=self.theme["accent"])
            for offset in (Inches(0.55), Inches(1.1), Inches(1.65)):
                self._add_rect(slide, left - Inches(0.16) + offset, top - Inches(0.16), Inches(0.02), height + Inches(0.32), self.theme["soft"], radius=False, transparency=55)
        elif frame_style == "blueprint_plate":
            self._add_rect(slide, left - Inches(0.2), top - Inches(0.2), width + Inches(0.4), height + Inches(0.4), self.theme["panel"], radius=False, line=self.theme["accent"])
            self._add_rect(slide, left - Inches(0.28), top - Inches(0.28), width + Inches(0.56), Inches(0.08), self.theme["accent2"], radius=False, transparency=38)
        elif frame_style == "folio_polaroid":
            self._add_rect(slide, left - Inches(0.18), top - Inches(0.18), width + Inches(0.36), height + Inches(0.5), self.theme["panel"], radius=True, line=self.theme["soft"])
            self._add_rect(slide, left - Inches(0.08), top + height + Inches(0.12), Inches(1.4), Inches(0.04), self.theme["accent"], radius=False, transparency=32)
        elif frame_style == "dark_stage":
            self._add_rect(slide, left - Inches(0.18), top - Inches(0.18), width + Inches(0.36), height + Inches(0.36), self.theme["panel"], radius=True, line=self.theme["accent"])
            self._add_rect(slide, left - Inches(0.08), top - Inches(0.08), width + Inches(0.16), height + Inches(0.16), self.theme["soft"], radius=True, transparency=72)
        elif frame_style == "archive_matte":
            self._add_rect(slide, left - Inches(0.22), top - Inches(0.22), width + Inches(0.44), height + Inches(0.44), self.theme["panel"], radius=False, line=self.theme["soft"])
            self._add_rect(slide, left - Inches(0.12), top + height + Inches(0.08), Inches(1.8), Inches(0.05), self.theme["accent2"], radius=False, transparency=36)
        else:
            self._add_rect(slide, left - Inches(0.14), top - Inches(0.14), width + Inches(0.28), height + Inches(0.28), self.theme["panel"], radius=True, line=self.theme["soft"])

    def _create_concept_slide(self, prs: Presentation, slide_data: Slide, lesson: LessonDeck, index: int):
        slide = self._blank(prs)
        self._slide_header(slide, slide_data, lesson, index)
        model = build_concept_render_model(slide_data)

        self._add_rect(slide, Inches(0.62), Inches(2.02), Inches(4.4), Inches(4.15), self.theme["panel"], radius=True, line=self.theme["soft"])
        self._add_text(slide, shorten(model.lead, 250), Inches(1.0), Inches(2.32), Inches(3.62), Inches(1.7), 23, True)
        self._add_text(slide, model.objective, Inches(1.0), Inches(4.28), Inches(3.6), Inches(0.9), 14, False, self.theme["muted"])
        self._add_rect(slide, Inches(0.98), Inches(5.32), Inches(1.22), Inches(0.08), self.theme["accent"], radius=False)

        self._add_rect(slide, Inches(5.4), Inches(2.02), Inches(7.25), Inches(4.15), self.theme["panel"], radius=True, line=self.theme["soft"])
        self._add_theme_divider(slide, Inches(5.88), Inches(2.28), Inches(2.6))
        self._add_section_list(slide, self._content_section_title(), model.supporting_points, Inches(5.88), Inches(2.43), Inches(6.15), Inches(3.35), max_items=6)
        self._add_notes(slide, slide_data)

    def _create_image_feature_slide(
        self,
        prs: Presentation,
        slide_data: Slide,
        lesson: LessonDeck,
        index: int,
        image_stream: BytesIO,
        attribution: Optional[str] = None,
    ):
        slide = self._blank(prs)
        self._slide_header(slide, slide_data, lesson, index, compact=True)

        image_box = (Inches(7.15), Inches(1.55), Inches(5.55), Inches(5.38))
        self._style_image_frame(slide, *image_box)
        placed = self._add_image(slide, image_stream, *image_box)

        lines = split_content(slide_data.content)
        lead = lines[0] if lines else slide_data.objective or slide_data.title
        if placed:
            self._add_text(slide, shorten(lead, 230), Inches(0.66), Inches(1.84), Inches(5.85), Inches(1.25), 24, True)
            self._add_theme_divider(slide, Inches(0.72), Inches(3.25), Inches(2.35))
            self._add_section_list(slide, "Key Points", lines[1:] or lines, Inches(0.72), Inches(3.42), Inches(5.6), Inches(2.75), max_items=5)
        else:
            self._add_rect(slide, Inches(0.62), Inches(1.88), Inches(12.0), Inches(4.75), self.theme["panel"], radius=True, line=self.theme["soft"])
            self._add_text(slide, shorten(lead, 270), Inches(1.02), Inches(2.28), Inches(5.05), Inches(1.35), 25, True)
            self._add_section_list(slide, "Key Points", lines[1:] or lines, Inches(6.55), Inches(2.3), Inches(5.25), Inches(3.45), max_items=6)
        if attribution:
            self._add_speaker_notes(slide, f"Image: {attribution}")
        self._add_notes(slide, slide_data)

    def _create_worked_example_slide(self, prs: Presentation, slide_data: Slide, lesson: LessonDeck, index: int):
        slide = self._blank(prs)
        self._slide_header(slide, slide_data, lesson, index, compact=True)

        headline = next((block.text for block in slide_data.contentBlocks if block.type == "headline" and block.text), slide_data.title)
        steps_block = next((block for block in slide_data.contentBlocks if block.type == "steps"), None)
        steps = list(steps_block.items) if steps_block and steps_block.items else split_content(slide_data.content)
        supporting = [line for line in split_content(slide_data.content) if line != headline]

        self._add_rect(slide, Inches(0.62), Inches(1.82), Inches(4.35), Inches(4.72), self.theme["panel"], radius=True, line=self.theme["soft"])
        self._add_text(slide, shorten(headline, 220), Inches(1.0), Inches(2.18), Inches(3.55), Inches(1.2), 23, True)
        self._add_text(
            slide,
            slide_data.objective or "Model the process before students try it independently.",
            Inches(1.0),
            Inches(3.55),
            Inches(3.5),
            Inches(1.15),
            14,
            False,
            self.theme["muted"],
        )

        self._add_rect(slide, Inches(5.32), Inches(1.82), Inches(7.3), Inches(4.72), self.theme["panel"], radius=True, line=self.theme["soft"])
        self._add_section_list(slide, "Steps", steps or ["Show each reasoning step clearly."], Inches(5.72), Inches(2.22), Inches(6.4), Inches(2.25), max_items=6)
        self._add_section_list(slide, "Teacher Prompt", supporting[:3] or [slide_data.content], Inches(5.72), Inches(4.72), Inches(6.4), Inches(1.25), max_items=3)
        self._add_notes(slide, slide_data)

    def _create_practice_slide(self, prs: Presentation, slide_data: Slide, lesson: LessonDeck, index: int):
        slide = self._blank(prs)
        self._slide_header(slide, slide_data, lesson, index, compact=True)
        model = build_practice_render_model(slide_data)
        self._add_rect(slide, Inches(0.62), Inches(1.82), Inches(12.0), Inches(1.55), self.theme["panel"], radius=True, line=self.theme["soft"])
        self._add_text(slide, shorten(model.question, 280), Inches(1.02), Inches(2.14), Inches(11.15), Inches(0.82), 23, True)

        self._add_rect(slide, Inches(0.62), Inches(3.72), Inches(5.68), Inches(2.9), self.theme["panel"], radius=True, line=self.theme["soft"])
        self._add_theme_divider(slide, Inches(1.02), Inches(3.98), Inches(2.25))
        self._add_section_list(slide, self._practice_section_title(), model.work_items, Inches(1.02), Inches(4.12), Inches(4.85), Inches(2.1), max_items=4)

        self._add_rect(slide, Inches(6.64), Inches(3.72), Inches(5.98), Inches(2.9), self.theme["soft"], radius=True)
        self._add_section_list(slide, "Teacher Key", model.teacher_key, Inches(7.04), Inches(4.12), Inches(5.1), Inches(2.1), max_items=4)
        self._add_notes(slide, slide_data)

    def _create_summary_slide(self, prs: Presentation, slide_data: Slide, lesson: LessonDeck, index: int):
        slide = self._blank(prs)
        self._slide_header(slide, slide_data, lesson, index)
        model = build_summary_render_model(slide_data)
        titles = list(self.theme.get("summary_labels", ("Remember", "Connect", "Apply Next")))
        for idx, items in enumerate(model.columns):
            left = Inches(0.62 + idx * 4.13)
            self._add_rect(slide, left, Inches(2.02), Inches(3.68), Inches(4.45), self.theme["panel"], radius=True, line=self.theme["soft"])
            self._add_theme_divider(slide, left + Inches(0.34), Inches(2.22), Inches(2.15))
            self._add_tag(slide, titles[idx], left + Inches(0.34), Inches(2.36), Inches(1.4), fill=self.theme["accent"] if idx != 1 else self.theme["accent2"])
            self._add_section_list(slide, "", items, left + Inches(0.34), Inches(2.84), Inches(3.0), Inches(3.0), max_items=5)
        self._add_notes(slide, slide_data)

    def _create_chart_slide(self, prs: Presentation, slide_data: Slide, lesson: LessonDeck, index: int, chart_info: Dict[str, Any]):
        slide = self._blank(prs)
        self._slide_header(slide, slide_data, lesson, index, compact=True)
        lines = split_content(slide_data.content)
        self._add_section_list(slide, "Read the Data", lines[:5], Inches(0.72), Inches(2.0), Inches(4.15), Inches(3.6), max_items=5)
        chart_added = self._add_chart(slide, chart_info, Inches(5.25), Inches(1.85), Inches(7.0), Inches(4.78))
        if not chart_added:
            self._add_rect(slide, Inches(5.25), Inches(1.85), Inches(7.0), Inches(4.78), self.theme["panel"], radius=True, line=self.theme["soft"])
            self._add_section_list(slide, "Discussion Prompts", lines[5:] or lines[:4], Inches(5.72), Inches(2.34), Inches(6.0), Inches(3.5), max_items=5)
        self._add_notes(slide, slide_data)

    def _create_closing_slide(self, prs: Presentation, lesson: LessonDeck):
        slide = self._blank(prs)
        self._add_rect(slide, Inches(0.78), Inches(0.78), Inches(11.78), Inches(5.95), self.theme["panel"], radius=True, line=self.theme["soft"])
        self._add_text(slide, "Ready for class", Inches(1.22), Inches(1.45), Inches(6.3), Inches(0.72), 38, True)
        self._add_text(slide, "Use the notes, activities, and visual prompts to adapt the lesson live.", Inches(1.25), Inches(2.32), Inches(7.0), Inches(0.55), 18, False, self.theme["muted"])
        self._add_section_list(
            slide,
            "Quick Finish",
            ["Ask one retrieval question", "Let students explain one visual", "Collect one exit-ticket response"],
            Inches(1.25),
            Inches(3.32),
            Inches(5.4),
            Inches(2.0),
            max_items=3,
        )
        self._add_rect(slide, Inches(8.65), Inches(1.54), Inches(2.6), Inches(2.6), self.theme["accent"], radius=True)
        self._add_text(slide, str(len(lesson.slides)), Inches(8.95), Inches(2.02), Inches(2.0), Inches(0.95), 48, True, (255, 255, 255), PP_ALIGN.CENTER)
        self._add_text(slide, "slides", Inches(8.95), Inches(3.08), Inches(2.0), Inches(0.35), 16, True, (255, 255, 255), PP_ALIGN.CENTER)

    async def _fetch_image(self, slide_data: Slide, subject: str) -> Tuple[Optional[BytesIO], Optional[str]]:
        if not slide_data.imageQuery:
            return None, None
        try:
            return await self.stock_photo_service.fetch_image(slide_data.imageQuery, orientation="landscape", subject=subject)
        except Exception as exc:
            logger.warning("Image fetch failed for %s: %s", slide_data.title, exc)
            return None, None

    def _add_image(self, slide, image_stream: BytesIO, left, top, width, height) -> bool:
        try:
            target_width = int(width / 9525)
            target_height = int(height / 9525)
            image_stream.seek(0)
            cropped = self.image_processor.center_crop(image_stream, target_width, target_height)
            cropped.seek(0)
            pic = slide.shapes.add_picture(cropped, left, top, width=width, height=height)
            try:
                pic.line.color.rgb = rgb(self.theme["soft"])
                pic.line.width = Pt(1)
            except Exception:
                pass
            return True
        except Exception as exc:
            logger.warning("Image placement failed: %s", exc)
            return False

    def _extract_chart_config(self, slide_data: Slide) -> Optional[Dict[str, Any]]:
        metadata = slide_data.visualMetadata
        if not metadata:
            return None
        visual_type = metadata.visualType if hasattr(metadata, "visualType") else metadata.get("visualType")
        if visual_type != "chart":
            return None
        visual_config = metadata.visualConfig if hasattr(metadata, "visualConfig") else metadata.get("visualConfig")
        generated = (visual_config or {}).get("generatedData", {})
        config = generated.get("config") or generated.get("chartConfig")
        if not config:
            return None
        return {"config": config, "chartType": generated.get("chartType", config.get("type", "bar"))}

    def _add_chart(self, slide, chart_info: Dict[str, Any], left, top, width, height) -> bool:
        config = chart_info["config"]
        chart_type = chart_info.get("chartType", "bar")
        labels = config.get("data", {}).get("labels", [])
        datasets = config.get("data", {}).get("datasets", [])
        if not labels or not datasets:
            return False

        data = CategoryChartData()
        data.categories = [str(label) for label in labels]
        for dataset in datasets[:3]:
            values = []
            for value in dataset.get("data", []):
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    values.append(0)
            data.add_series(str(dataset.get("label", "Series")), values)

        ppt_chart_type = {
            "line": XL_CHART_TYPE.LINE_MARKERS,
            "pie": XL_CHART_TYPE.PIE,
            "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
            "scatter": XL_CHART_TYPE.XY_SCATTER_LINES,
        }.get(chart_type, XL_CHART_TYPE.COLUMN_CLUSTERED)

        chart = slide.shapes.add_chart(ppt_chart_type, left, top, width, height, data).chart
        chart.has_legend = len(datasets) > 1 or chart_type == "pie"
        if chart.has_legend:
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
        chart.chart_title.has_text_frame = True
        chart.chart_title.text_frame.text = clean_text(config.get("options", {}).get("plugins", {}).get("title", {}).get("text", ""))
        for series_idx, series in enumerate(chart.series):
            palette = [self.theme["accent"], self.theme["accent2"], self.theme["muted"]]
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = rgb(palette[series_idx % len(palette)])
        return True

    def _add_notes(self, slide, slide_data: Slide):
        if slide_data.speakerNotes:
            self._add_speaker_notes(slide, slide_data.speakerNotes)

    def _add_speaker_notes(self, slide, notes: str):
        try:
            slide.notes_slide.notes_text_frame.text = clean_text(notes)
        except Exception as exc:
            logger.warning("Failed to add speaker notes: %s", exc)


async def render_deck_to_pptx(lesson: LessonDeck, theme: str = "default") -> BytesIO:
    renderer = PPTXRenderer(theme=theme)
    return await renderer.render_lesson_deck(lesson)
