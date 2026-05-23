import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


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


if __name__ == "__main__":
    unittest.main()
