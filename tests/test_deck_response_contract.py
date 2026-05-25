import unittest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
from io import BytesIO

from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.models.lesson_schema import DeckGenerateResponse
from app.services.layout_selector import select_layout_for_slide


class DeckResponseContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_generate_deck_returns_canonical_response(self):
        payload = {
            "topic": "Newton's First Law",
            "subject": "Physics",
            "gradeLevel": "9",
            "theme": "default",
        }
        ai_result = {
            "title": "Newton's First Law",
            "slides": [
                {
                    "title": "Introduction to Newton's First Law",
                    "content": "Objects remain at rest unless acted on by a force.",
                    "order": 1,
                    "slideType": "INTRODUCTION",
                    "bloom_level": "UNDERSTAND",
                    "objective": "Explain inertia in simple terms.",
                }
            ],
        }

        with patch("app.routers.deck.generate_json_completion", new=AsyncMock(return_value=ai_result)), \
             patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}])), \
             patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}])):
            response = self.client.post("/api/deck/generate-deck", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("lesson", body)
        self.assertEqual(body["title"], "Newton's First Law")
        self.assertEqual(body["lesson"]["meta"]["topic"], "Newton's First Law")
        self.assertEqual(len(body["slides"]), 1)

    def test_modify_deck_returns_canonical_response(self):
        payload = {
            "subject": "Physics",
            "gradeLevel": "9",
            "feedback": "Make the slide shorter.",
            "currentDeck": {
                "title": "Newton's First Law",
                "slides": [
                    {
                        "title": "Old Slide",
                        "content": "Old content",
                        "order": 1,
                    }
                ],
            },
        }
        ai_result = {
            "title": "Newton's First Law",
            "slides": [
                {
                    "title": "Revised Slide",
                    "content": "Objects keep their motion unless a force changes it.",
                    "order": 1,
                    "slideType": "CONCEPT",
                    "bloom_level": "UNDERSTAND",
                    "objective": "State Newton's first law.",
                }
            ],
        }

        with patch("app.routers.deck.generate_json_completion", new=AsyncMock(return_value=ai_result)), \
             patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}])), \
             patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}])):
            response = self.client.post("/api/deck/modify-deck", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("lesson", body)
        self.assertEqual(body["lesson"]["meta"]["topic"], "Newton's First Law")
        self.assertEqual(body["slides"][0]["title"], "Revised Slide")

    def test_regenerate_cluster_returns_canonical_response(self):
        payload = {
            "deckId": "deck_1",
            "clusterId": "explain_1",
            "pedagogicalRole": "explain_deepen",
            "theme": "blueprint",
            "subject": "Physics",
            "gradeLevel": "9",
            "currentDeck": {
                "title": "Newton's First Law",
                "lesson": {
                    "meta": {
                        "topic": "Newton's First Law",
                        "subject": "Physics",
                        "grade": "9",
                        "theme": "blueprint",
                    },
                    "structure": {
                        "learning_objectives": [],
                        "vocabulary": [],
                        "prerequisites": [],
                        "bloom_progression": [],
                    },
                    "slides": [
                        {
                            "title": "Concept 1",
                            "content": "Old content",
                            "order": 1,
                            "slideType": "CONCEPT",
                            "bloom_level": "UNDERSTAND",
                            "clusterId": "explain_1",
                            "pedagogicalRole": "explain_core",
                            "layoutCandidates": ["concept-with-image"],
                        }
                    ],
                },
            },
        }
        ai_result = {
            "title": "Newton's First Law",
            "meta": payload["currentDeck"]["lesson"]["meta"],
            "structure": payload["currentDeck"]["lesson"]["structure"],
            "slides": [
                {
                    "title": "Concept 1",
                    "content": "Old content",
                    "order": 1,
                    "slideType": "CONCEPT",
                    "bloom_level": "UNDERSTAND",
                    "clusterId": "explain_1",
                    "pedagogicalRole": "explain_core",
                    "layoutCandidates": ["concept-with-image"],
                },
                {
                    "title": "Concept 1 Explain More",
                    "content": "More explanation",
                    "order": 2,
                    "slideType": "CONCEPT",
                    "bloom_level": "UNDERSTAND",
                    "clusterId": "explain_1",
                    "pedagogicalRole": "explain_deepen",
                    "layoutCandidates": ["two-column-explain"],
                },
            ],
        }

        with patch("app.routers.deck.generate_json_completion", new=AsyncMock(return_value=ai_result)), \
             patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}, {}])), \
             patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}, {"success": False}])):
            response = self.client.post("/api/deck/regenerate-cluster", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("lesson", body)
        self.assertEqual(body["title"], "Newton's First Law")
        self.assertEqual(body["slides"][1]["clusterId"], "explain_1")
        self.assertEqual(body["slides"][1]["pedagogicalRole"], "explain_deepen")
        self.assertEqual(body["slides"][1]["layoutCandidates"], ["two-column-explain"])

    def test_modify_deck_preserves_existing_visual_metadata_when_visual_regeneration_fails(self):
        payload = {
            "subject": "Physics",
            "gradeLevel": "9",
            "feedback": "Make the slide shorter.",
            "currentDeck": {
                "title": "Newton's First Law",
                "lesson": {
                    "meta": {
                        "topic": "Newton's First Law",
                        "subject": "Physics",
                        "grade": "9",
                        "theme": "blueprint",
                    },
                    "structure": {
                        "learning_objectives": [],
                        "vocabulary": [],
                        "prerequisites": [],
                        "bloom_progression": [],
                    },
                    "slides": [
                        {
                            "id": "slide_1",
                            "title": "Revised Slide",
                            "content": "Old content",
                            "order": 1,
                            "slideType": "CONCEPT",
                            "bloom_level": "UNDERSTAND",
                            "visualMetadata": {
                                "visualType": "diagram",
                                "visualConfig": {
                                    "selectedLayout": "concept-with-image",
                                },
                                "confidence": 0.8,
                            },
                        }
                    ],
                },
            },
        }
        ai_result = {
            "title": "Newton's First Law",
            "slides": [
                {
                    "id": "slide_1",
                    "title": "Revised Slide",
                    "content": "Objects keep their motion unless a force changes it.",
                    "order": 1,
                    "slideType": "CONCEPT",
                    "bloom_level": "UNDERSTAND",
                }
            ],
        }

        with patch("app.routers.deck.generate_json_completion", new=AsyncMock(return_value=ai_result)), \
             patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}])), \
             patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}])):
            response = self.client.post("/api/deck/modify-deck", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["slides"][0]["visualMetadata"]["visualType"], "diagram")
        self.assertEqual(
            body["slides"][0]["visualMetadata"]["visualConfig"]["selectedLayout"],
            "concept-with-image",
        )

    def test_render_pptx_renders_a_canonical_lesson_deck_via_dedicated_route(self):
        payload = {
            "theme": "blueprint",
            "lesson": {
                "meta": {
                    "topic": "Newton's First Law",
                    "subject": "Physics",
                    "grade": "9",
                    "theme": "blueprint",
                },
                "structure": {
                    "learning_objectives": [],
                    "vocabulary": [],
                    "prerequisites": [],
                    "bloom_progression": [],
                },
                "slides": [
                    {
                        "title": "Concept 1",
                        "content": "Force changes motion.",
                        "order": 1,
                        "slideType": "CONCEPT",
                        "bloom_level": "UNDERSTAND",
                    }
                ],
            },
        }

        with patch("app.routers.deck.PPTXRenderer") as renderer_cls:
            renderer_instance = renderer_cls.return_value
            renderer_instance.render_lesson_deck = AsyncMock(return_value=BytesIO(b"pptx-bytes"))

            response = self.client.post("/api/deck/render-pptx", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        renderer_cls.assert_called_once_with(theme="blueprint")
        renderer_instance.render_lesson_deck.assert_awaited_once()
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        self.assertIn("attachment; filename=Newton's_First_Law_deck.pptx", response.headers["content-disposition"])
        self.assertEqual(response.content, b"pptx-bytes")

    def test_structured_slide_schema_fields_are_present(self):
        payload = DeckGenerateResponse.model_validate({
            "lesson": {
                "meta": {
                    "topic": "Newton's Laws",
                    "subject": "Physics",
                    "grade": "9",
                    "theme": "blueprint",
                    "standards": [],
                    "pedagogical_model": "I_DO_WE_DO_YOU_DO",
                },
                "structure": {
                    "learning_objectives": [],
                    "vocabulary": [],
                    "prerequisites": [],
                    "bloom_progression": [],
                },
                "slides": [{
                    "title": "Try It Together",
                    "content": "Legacy compatibility text",
                    "order": 1,
                    "slideType": "ACTIVITY",
                    "bloom_level": "APPLY",
                    "clusterId": "guided_practice_1",
                    "pedagogicalRole": "guided_practice",
                    "instructionalGoal": "Apply Newton's first law to a classroom scenario.",
                    "contentMode": "question",
                    "layoutCandidates": ["guided-practice"],
                    "density": "medium",
                    "importance": "primary",
                    "contentBlocks": [
                        {"type": "headline", "text": "Try It Together"},
                        {"type": "question", "text": "What force acts here?"},
                    ],
                    "visualIntent": {
                        "purpose": "clarify",
                        "assetType": "none",
                        "priority": "optional",
                        "sourceStrategy": "renderer_native",
                    },
                    "editingHints": {
                        "locked": False,
                        "canAddBlocks": ["hint"],
                        "canRemoveBlocks": ["answer"],
                    },
                    "practiceMetadata": {
                        "difficulty": "medium",
                        "answerMode": "hidden_by_default",
                        "stepCount": 3,
                        "misconception": "Objects in motion need a constant force to keep moving.",
                    },
                }],
            },
            "slides": [],
        })

        slide = payload.lesson.slides[0]

        self.assertEqual(slide.clusterId, "guided_practice_1")
        self.assertEqual(slide.pedagogicalRole, "guided_practice")
        self.assertEqual(slide.instructionalGoal, "Apply Newton's first law to a classroom scenario.")
        self.assertEqual(slide.contentMode, "question")
        self.assertEqual(slide.layoutCandidates, ["guided-practice"])
        self.assertEqual(slide.density, "medium")
        self.assertEqual(slide.importance, "primary")
        self.assertEqual(len(slide.contentBlocks), 2)
        self.assertEqual(slide.contentBlocks[0].type, "headline")
        self.assertEqual(slide.contentBlocks[0].text, "Try It Together")
        self.assertEqual(slide.contentBlocks[0].items, [])
        self.assertEqual(slide.contentBlocks[0].value, None)
        self.assertEqual(slide.contentBlocks[1].type, "question")
        self.assertEqual(slide.contentBlocks[1].text, "What force acts here?")
        self.assertEqual(slide.contentBlocks[1].items, [])
        self.assertEqual(slide.contentBlocks[1].value, None)
        self.assertEqual(slide.visualIntent.purpose, "clarify")
        self.assertEqual(slide.visualIntent.assetType, "none")
        self.assertEqual(slide.visualIntent.priority, "optional")
        self.assertEqual(slide.visualIntent.sourceStrategy, "renderer_native")
        self.assertEqual(slide.editingHints.locked, False)
        self.assertEqual(slide.editingHints.canAddBlocks, ["hint"])
        self.assertEqual(slide.editingHints.canRemoveBlocks, ["answer"])
        self.assertEqual(slide.practiceMetadata.difficulty, "medium")
        self.assertEqual(slide.practiceMetadata.answerMode, "hidden_by_default")
        self.assertEqual(slide.practiceMetadata.stepCount, 3)
        self.assertEqual(
            slide.practiceMetadata.misconception,
            "Objects in motion need a constant force to keep moving.",
        )

    def test_structured_slide_schema_rejects_invalid_controlled_values(self):
        with self.assertRaises(ValidationError):
            DeckGenerateResponse.model_validate({
                "lesson": {
                    "meta": {
                        "topic": "Newton's Laws",
                        "subject": "Physics",
                        "grade": "9",
                    },
                    "structure": {
                        "learning_objectives": [],
                        "vocabulary": [],
                        "prerequisites": [],
                        "bloom_progression": [],
                    },
                    "slides": [{
                        "title": "Try It Together",
                        "content": "Legacy compatibility text",
                        "order": 1,
                        "visualIntent": {
                            "purpose": "clarify",
                            "assetType": "none",
                            "priority": "maybe",
                            "sourceStrategy": "magic",
                        },
                        "density": "dense",
                        "importance": "critical",
                    }],
                },
                "slides": [],
            })

    def test_rejected_visual_slide_keeps_structured_metadata_and_text_layout_candidates(self):
        payload = DeckGenerateResponse.model_validate({
            "lesson": {
                "meta": {
                    "topic": "Plant Cells",
                    "subject": "Biology",
                    "grade": "8",
                    "theme": "default",
                },
                "structure": {
                    "learning_objectives": [],
                    "vocabulary": [],
                    "prerequisites": [],
                    "bloom_progression": [],
                },
                "slides": [{
                    "title": "Cell Membrane",
                    "content": "The cell membrane controls what enters and leaves the cell.",
                    "order": 1,
                    "clusterId": "explain_1",
                    "pedagogicalRole": "explain_core",
                    "instructionalGoal": "Explain the function of the cell membrane.",
                    "contentMode": "image_support",
                    "layoutCandidates": ["concept-with-image", "concept-focus"],
                    "contentBlocks": [
                        {"type": "headline", "text": "Cell Membrane"},
                    ],
                    "visualIntent": {
                        "purpose": "explain",
                        "assetType": "photo",
                        "priority": "optional",
                        "sourceStrategy": "stock",
                    },
                    "editingHints": {
                        "locked": False,
                        "canAddBlocks": [],
                        "canRemoveBlocks": [],
                        "notes": {"cluster_status": "teacher_review"},
                    },
                    "imageQuery": "plant",
                }],
            },
            "slides": [],
        })

        slide = payload.lesson.slides[0]
        selected = select_layout_for_slide(slide=slide, theme=payload.lesson.meta.theme)

        self.assertEqual(selected.layout_id, "concept-focus")
        self.assertEqual(slide.layoutCandidates, ["concept-with-image", "concept-focus"])
        self.assertIsNotNone(slide.editingHints)
        self.assertEqual(slide.editingHints.notes["cluster_status"], "teacher_review")
        self.assertEqual(slide.editingHints.notes["visual_state"], "visual_rejected")


if __name__ == "__main__":
    unittest.main()
