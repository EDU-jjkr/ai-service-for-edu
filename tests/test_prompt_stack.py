import sys
from pathlib import Path
import asyncio
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app
from app.agents.deck_agents import ContentAgent, OutlinerAgent
from app.models.lesson_schema import LessonDeck, LessonMetadata, LearningStructure
from app.services.prompt_stack import (
    PromptBundle,
    build_lesson_planner_prompt,
    build_slide_author_prompt,
    build_visual_intent_prompt,
)


def test_lesson_planner_prompt_includes_topic_grade_and_flow():
    prompt = build_lesson_planner_prompt(
        topic="Quadratic Equations",
        subject="Mathematics",
        grade_level="10",
        chapter="Polynomials",
        pedagogy_flow="problem_solving_math",
        additional_instructions="include more practice",
    )

    assert "Quadratic Equations" in prompt.user_prompt
    assert "problem_solving_math" in prompt.user_prompt
    assert "include more practice" in prompt.user_prompt
    assert "OUTPUT BUDGET POLICY" in prompt.system_prompt


def test_slide_author_prompt_separates_lesson_plan_from_slide_authoring():
    prompt = build_slide_author_prompt(
        topic="Photosynthesis",
        subject="Biology",
        grade_level="8",
        pedagogical_role="explain_core",
        instructional_goal="Explain how light energy becomes stored chemical energy.",
    )

    assert "pedagogical_role: explain_core" in prompt.user_prompt
    assert "instructional_goal" in prompt.user_prompt
    assert "Do not plan the full lesson again" in prompt.system_prompt


def test_visual_intent_prompt_uses_role_and_content_mode_contract():
    prompt = build_visual_intent_prompt(
        slide_title="Newton's First Law Demo",
        pedagogical_role="hook",
        content_mode="image_support",
        subject="Physics",
    )

    assert "hook" in prompt.user_prompt
    assert "image_support" in prompt.user_prompt
    assert "Return JSON only" in prompt.system_prompt


def test_generation_path_uses_prompt_bundle_at_runtime(monkeypatch):
    captured = {}

    async def fake_stream_completion(prompt, system_message, max_tokens=800):
        captured["prompt"] = prompt
        captured["system_message"] = system_message
        yield "Generated from prompt stack"

    monkeypatch.setattr("app.agents.deck_agents.stream_completion", fake_stream_completion)
    monkeypatch.setattr(
        ContentAgent,
        "generate_speaker_notes",
        AsyncMock(return_value="Teacher note"),
    )
    monkeypatch.setattr(
        "app.agents.visual_director_agent.VisualDirectorAgent.generate_image_query",
        AsyncMock(return_value={"imageQuery": "diagram"}),
    )

    slide_plan = {
        "title": "Photosynthesis Core",
        "slideType": "CONCEPT",
        "bloom_level": "UNDERSTAND",
        "objective": "Explain the process.",
        "prompt_stack": PromptBundle(
            system_prompt="PROMPT STACK SYSTEM",
            user_prompt="PROMPT STACK USER",
        ),
    }

    result = asyncio.run(
        ContentAgent.generate_all_slides_parallel(
            outline=[slide_plan],
            subject="Biology",
            grade_level="8",
        )
    )

    assert result[0]["content"] == "Generated from prompt stack"
    assert captured["prompt"].startswith("PROMPT STACK USER")
    assert captured["system_message"].startswith("PROMPT STACK SYSTEM")


def test_outline_generation_uses_planner_prompt_bundle_at_runtime(monkeypatch):
    captured = {}

    async def fake_generate_json_completion(prompt, system_message, max_tokens=1200):
        captured["prompt"] = prompt
        captured["system_message"] = system_message
        return {
            "slides": [
                {
                    "title": "Quadratic Equations Overview",
                    "slideType": "INTRODUCTION",
                    "bloom_level": "REMEMBER",
                    "objective": "Define quadratic equations.",
                }
            ]
        }

    monkeypatch.setattr(
        "app.agents.deck_agents.generate_json_completion",
        fake_generate_json_completion,
    )

    class FakeRag:
        async def retrieve_relevant_standards(self, **kwargs):
            return []

        def inject_into_prompt(self, standards, prompt):
            return prompt

    monkeypatch.setattr(
        "app.services.rag_service.get_curriculum_rag",
        lambda: FakeRag(),
    )

    prompt_bundle = PromptBundle(
        system_prompt="PLANNER STACK SYSTEM",
        user_prompt="PLANNER STACK USER",
    )

    result = asyncio.run(
        OutlinerAgent.create_outline(
            topic="Quadratic Equations",
            subject="Mathematics",
            grade_level="10",
            prompt_bundle=prompt_bundle,
        )
    )

    assert result[0]["title"] == "Quadratic Equations Overview"
    assert "PLANNER STACK USER" in captured["prompt"]
    assert captured["prompt"].startswith("PLANNER STACK USER")
    assert "PLANNER STACK SYSTEM" in captured["system_message"]
    assert captured["system_message"].startswith("PLANNER STACK SYSTEM")


def test_generate_complete_endpoint_delegates_to_planner_driven_generation(monkeypatch):
    client = TestClient(app)
    planned_deck = LessonDeck(
        meta=LessonMetadata(
            topic="Photosynthesis",
            subject="Biology",
            grade="8",
            standards=[],
            theme="default",
            pedagogical_model="I_DO_WE_DO_YOU_DO",
        ),
        structure=LearningStructure(
            learning_objectives=[],
            vocabulary=[],
            prerequisites=[],
            bloom_progression=[],
        ),
        slides=[],
    )

    planner_mock = AsyncMock(return_value=planned_deck)
    monkeypatch.setattr("app.routers.deck._generate_planned_lesson_deck", planner_mock)
    monkeypatch.setattr("app.routers.deck.apply_quality_guards_to_lesson", lambda lesson: lesson)

    response = client.post(
        "/api/deck/generate-complete",
        json={
            "topic": "Photosynthesis",
            "subject": "Biology",
            "gradeLevel": "8",
            "theme": "default",
        },
    )

    assert response.status_code == 200, response.text
    planner_mock.assert_awaited_once()
    body = response.json()
    assert body["meta"]["topic"] == "Photosynthesis"


def test_generate_level_endpoint_delegates_to_planner_driven_generation(monkeypatch):
    client = TestClient(app)
    planned_deck = LessonDeck(
        meta=LessonMetadata(
            topic="Photosynthesis",
            subject="Biology",
            grade="8",
            standards=[],
            theme="default",
            pedagogical_model="I_DO_WE_DO_YOU_DO",
        ),
        structure=LearningStructure(
            learning_objectives=[],
            vocabulary=[],
            prerequisites=[],
            bloom_progression=[],
        ),
        slides=[],
    )
    differentiated_deck = LessonDeck(
        meta=LessonMetadata(
            topic="Photosynthesis",
            subject="Biology",
            grade="8",
            standards=[],
            theme="default",
            pedagogical_model="I_DO_WE_DO_YOU_DO",
        ),
        structure=LearningStructure(
            learning_objectives=[],
            vocabulary=[],
            prerequisites=[],
            bloom_progression=[],
        ),
        slides=[],
    )

    class FakeDifferentiationService:
        async def generate_differentiated_deck(self, core_deck, target_level):
            return differentiated_deck

    planner_mock = AsyncMock(return_value=planned_deck)
    monkeypatch.setattr("app.routers.deck._generate_planned_lesson_deck", planner_mock)
    monkeypatch.setattr("app.routers.deck.apply_quality_guards_to_lesson", lambda lesson: lesson)
    monkeypatch.setattr(
        "app.services.differentiation.DifferentiationService",
        FakeDifferentiationService,
    )

    response = client.post(
        "/api/deck/generate-level/extension",
        json={
            "topic": "Photosynthesis",
            "subject": "Biology",
            "gradeLevel": "8",
            "theme": "default",
        },
    )

    assert response.status_code == 200, response.text
    planner_mock.assert_awaited_once()
    body = response.json()
    assert body["meta"]["topic"] == "Photosynthesis"
