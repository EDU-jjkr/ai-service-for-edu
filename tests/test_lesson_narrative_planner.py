import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.models.lesson_schema import ContentMode, PedagogicalRole, Slide
from app.services.deck_schema_builder import build_structured_slides_from_plan
from app.services.lesson_narrative_planner import (
    LessonNarrativePlan,
    NarrativeCluster,
    build_lesson_narrative_plan,
)


def test_planner_creates_required_clusters_for_standard_topic():
    plan = build_lesson_narrative_plan(
        topic="Newton's Laws",
        subject="Physics",
        grade_level="9",
        chapter="Force and Motion",
        additional_instructions=None,
    )

    cluster_kinds = [cluster.kind for cluster in plan.clusters]

    assert cluster_kinds == [
        "hook",
        "explain",
        "example",
        "guided_practice",
        "independent_practice",
        "summary",
    ]
    assert next(cluster for cluster in plan.clusters if cluster.kind == "explain").slide_count >= 2
    assert next(cluster for cluster in plan.clusters if cluster.kind == "guided_practice").slide_count >= 2


def test_planner_preserves_topic_by_topic_sequence_for_multi_topic_requests():
    plan = build_lesson_narrative_plan(
        topic=["Newton's First Law", "Newton's Second Law"],
        subject="Physics",
        grade_level="9",
        chapter="Force and Motion",
        additional_instructions=None,
    )

    cluster_topics = [cluster.subtopics[0] for cluster in plan.clusters if cluster.kind != "summary"]

    assert cluster_topics[:5] == [
        "Newton's First Law",
        "Newton's First Law",
        "Newton's First Law",
        "Newton's First Law",
        "Newton's First Law",
    ]
    assert cluster_topics[5:10] == [
        "Newton's Second Law",
        "Newton's Second Law",
        "Newton's Second Law",
        "Newton's Second Law",
        "Newton's Second Law",
    ]


def test_planner_uses_grade_chapter_and_additional_instructions():
    base_plan = build_lesson_narrative_plan(
        topic="Chemical Reactions",
        subject="Chemistry",
        grade_level="6",
        chapter=None,
        additional_instructions=None,
    )
    influenced_plan = build_lesson_narrative_plan(
        topic="Chemical Reactions",
        subject="Chemistry",
        grade_level="12",
        chapter="Organic Chemistry",
        additional_instructions="Add extra practice and challenge work.",
    )

    base_guided = next(cluster for cluster in base_plan.clusters if cluster.kind == "guided_practice")
    influenced_guided = next(cluster for cluster in influenced_plan.clusters if cluster.kind == "guided_practice")

    assert influenced_guided.slide_count > base_guided.slide_count
    assert influenced_plan.clusters[0].subtopics[0] == "Organic Chemistry"


def test_schema_builder_emits_structured_guided_practice_slide():
    plan = LessonNarrativePlan(
        clusters=[
            NarrativeCluster(
                kind="guided_practice",
                slide_count=1,
                subtopics=["Newton's First Law"],
            )
        ]
    )

    slides = build_structured_slides_from_plan(
        plan=plan,
        subject="Physics",
        grade_level="9",
    )

    assert slides[0].pedagogicalRole == PedagogicalRole.GUIDED_PRACTICE
    assert slides[0].contentMode == ContentMode.QUESTION
    assert "guided-practice" in slides[0].layoutCandidates


def test_generate_deck_uses_planner_driven_structured_slides():
    client = TestClient(app)
    planned_slide = Slide(
        title="Planner Shell",
        content="placeholder",
        order=1,
        clusterId="guided_practice_1",
        pedagogicalRole=PedagogicalRole.GUIDED_PRACTICE,
        contentMode=ContentMode.QUESTION,
        layoutCandidates=["guided-practice"],
    )

    with patch("app.agents.deck_agents.OutlinerAgent.create_outline", new=AsyncMock(return_value=[])), \
         patch("app.agents.deck_agents.ContentAgent.generate_all_slides_parallel", new=AsyncMock(return_value=[{
             "title": "Generated Title",
             "content": "Generated content",
             "order": 1,
             "slideType": "ACTIVITY",
             "bloom_level": "APPLY",
             "speakerNotes": "Notes",
             "imageQuery": "query",
             "objective": "Objective",
         }])), \
         patch("app.routers.deck.build_lesson_narrative_plan") as planner_mock, \
         patch("app.routers.deck.build_structured_slides_from_plan", return_value=[planned_slide]) as builder_mock, \
         patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}])), \
         patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}])):
        response = client.post(
            "/api/deck/generate-deck",
            json={
                "topic": "Newton's First Law",
                "subject": "Physics",
                "gradeLevel": "9",
                "structuredFormat": True,
                "theme": "default",
            },
        )

    assert response.status_code == 200, response.text
    assert planner_mock.called
    assert builder_mock.called
    body = response.json()
    assert body["slides"][0]["title"] == "Generated Title"
    assert body["slides"][0]["clusterId"] == "guided_practice_1"
    assert body["slides"][0]["pedagogicalRole"] == "guided_practice"
    assert body["slides"][0]["content"] == "Generated content"


def test_generate_deck_preserves_extra_outliner_structure():
    client = TestClient(app)
    planned_slide = Slide(
        title="Planner Shell",
        content="placeholder",
        order=1,
        clusterId="explain_1",
    )

    with patch("app.agents.deck_agents.OutlinerAgent.create_outline", new=AsyncMock(return_value=[
        {
            "title": "Generated Title 1",
            "slideType": "CONCEPT",
            "bloom_level": "UNDERSTAND",
            "objective": "Objective 1",
        },
        {
            "title": "Generated Title 2",
            "slideType": "ACTIVITY",
            "bloom_level": "APPLY",
            "objective": "Objective 2",
        },
    ])), \
         patch("app.agents.deck_agents.ContentAgent.generate_all_slides_parallel", new=AsyncMock(return_value=[
             {
                 "title": "Generated Title 1",
                 "content": "Generated content 1",
                 "order": 1,
                 "slideType": "CONCEPT",
                 "bloom_level": "UNDERSTAND",
                 "speakerNotes": "Notes 1",
                 "imageQuery": None,
                 "objective": "Objective 1",
             },
             {
                 "title": "Generated Title 2",
                 "content": "Generated content 2",
                 "order": 2,
                 "slideType": "ACTIVITY",
                 "bloom_level": "APPLY",
                 "speakerNotes": "Notes 2",
                 "imageQuery": None,
                 "objective": "Objective 2",
             },
         ])), \
         patch("app.routers.deck.build_lesson_narrative_plan"), \
         patch("app.routers.deck.build_structured_slides_from_plan", return_value=[planned_slide]), \
         patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}, {}])), \
         patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}, {"success": False}])):
        response = client.post(
            "/api/deck/generate-deck",
            json={
                "topic": "Newton's Laws",
                "subject": "Physics",
                "gradeLevel": "9",
                "structuredFormat": True,
                "theme": "default",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["slides"]) == 2
    assert body["slides"][1]["title"] == "Generated Title 2"
    assert body["slides"][1]["objective"] == "Objective 2"


def test_generate_complete_deck_respects_requested_num_slides():
    client = TestClient(app)
    planned_slides = [
        Slide(title="Hook", content="placeholder", order=1, slideType="INTRODUCTION"),
        Slide(title="Explain", content="placeholder", order=2, slideType="CONCEPT"),
        Slide(title="Practice", content="placeholder", order=3, slideType="ACTIVITY"),
        Slide(title="Summary", content="placeholder", order=4, slideType="SUMMARY"),
    ]
    outliner_mock = AsyncMock(return_value=[
        {
            "title": "Hook",
            "slideType": "INTRODUCTION",
            "bloom_level": "REMEMBER",
            "objective": "Objective 1",
        },
        {
            "title": "Explain",
            "slideType": "CONCEPT",
            "bloom_level": "UNDERSTAND",
            "objective": "Objective 2",
        },
        {
            "title": "Practice",
            "slideType": "ACTIVITY",
            "bloom_level": "APPLY",
            "objective": "Objective 3",
        },
        {
            "title": "Summary",
            "slideType": "SUMMARY",
            "bloom_level": "CREATE",
            "objective": "Objective 4",
        },
    ])

    with patch("app.agents.deck_agents.OutlinerAgent.create_outline", new=outliner_mock), \
         patch("app.agents.deck_agents.ContentAgent.generate_all_slides_parallel", new=AsyncMock(return_value=[
             {
                 "title": "Hook",
                 "content": "Generated content 1",
                 "order": 1,
                 "slideType": "INTRODUCTION",
                 "bloom_level": "REMEMBER",
                 "speakerNotes": "Notes 1",
                 "imageQuery": None,
                 "objective": "Objective 1",
             },
             {
                 "title": "Explain",
                 "content": "Generated content 2",
                 "order": 2,
                 "slideType": "CONCEPT",
                 "bloom_level": "UNDERSTAND",
                 "speakerNotes": "Notes 2",
                 "imageQuery": None,
                 "objective": "Objective 2",
             },
             {
                 "title": "Summary",
                 "content": "Generated content 3",
                 "order": 3,
                 "slideType": "SUMMARY",
                 "bloom_level": "CREATE",
                 "speakerNotes": "Notes 3",
                 "imageQuery": None,
                 "objective": "Objective 3",
             },
         ])), \
         patch("app.routers.deck.build_lesson_narrative_plan"), \
         patch("app.routers.deck.build_structured_slides_from_plan", return_value=planned_slides), \
         patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}, {}, {}])), \
         patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}, {"success": False}, {"success": False}])):
        response = client.post(
            "/api/deck/generate-complete",
            json={
                "topic": "Gymnosperms",
                "subject": "Biology",
                "gradeLevel": "11",
                "structuredFormat": True,
                "theme": "default",
                "numSlides": 3,
            },
        )

    assert response.status_code == 200, response.text
    assert outliner_mock.await_args.kwargs["target_slide_count"] == 3
    body = response.json()
    assert len(body["slides"]) == 3
    assert body["slides"][-1]["slideType"] == "SUMMARY"


def test_generate_all_levels_handles_slide_objects_without_dict_access():
    client = TestClient(app)
    planned_slide = Slide(
        title="Planner Shell",
        content="placeholder",
        order=1,
    )
    generated_slide = {
        "title": "Generated Title",
        "content": "Generated content",
        "order": 1,
        "slideType": "CONCEPT",
        "bloom_level": "UNDERSTAND",
        "objective": "Explain inertia",
    }

    with patch("app.agents.deck_agents.OutlinerAgent.create_outline", new=AsyncMock(return_value=[])), \
         patch("app.agents.deck_agents.ContentAgent.generate_all_slides_parallel", new=AsyncMock(return_value=[generated_slide])), \
         patch("app.routers.deck.build_lesson_narrative_plan"), \
         patch("app.routers.deck.build_structured_slides_from_plan", return_value=[planned_slide]), \
         patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}])), \
         patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}])), \
         patch("app.services.differentiation.DifferentiationService.generate_differentiated_deck", new=AsyncMock(side_effect=lambda core_deck, target_level: core_deck)):
        response = client.post(
            "/api/deck/generate-all-levels",
            json={
                "topic": "Newton's First Law",
                "subject": "Physics",
                "gradeLevel": "9",
                "theme": "default",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["core"]["slides"][0]["objective"] == "Explain inertia"
