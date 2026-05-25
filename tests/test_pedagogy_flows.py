import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.models.lesson_schema import ContentMode, PedagogicalRole, Slide
from app.services.lesson_narrative_planner import build_lesson_narrative_plan


def test_math_problem_solving_flow_reorders_clusters():
    plan = build_lesson_narrative_plan(
        topic="Quadratic Equations",
        subject="Mathematics",
        grade_level="10",
        chapter="Polynomials",
        additional_instructions="problem solving flow",
        pedagogy_flow="problem_solving_math",
    )

    cluster_kinds = [cluster.kind for cluster in plan.clusters[:4]]

    assert cluster_kinds == ["hook", "example", "guided_practice", "explain"]


def test_revision_flow_adds_extra_practice_and_summary():
    plan = build_lesson_narrative_plan(
        topic="Cell Division",
        subject="Biology",
        grade_level="10",
        chapter="Cell Biology",
        additional_instructions="exam revision deck",
        pedagogy_flow="revision_exam_prep",
    )

    assert sum(1 for cluster in plan.clusters if cluster.kind == "guided_practice") >= 2
    assert plan.clusters[-1].kind == "summary"


def test_generate_complete_deck_passes_requested_pedagogy_flow_to_planner():
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
         patch("app.routers.deck.build_structured_slides_from_plan", return_value=[planned_slide]), \
         patch("app.routers.deck.batch_route_slides", new=AsyncMock(return_value=[{}])), \
         patch("app.routers.deck.batch_generate_visuals", new=AsyncMock(return_value=[{"success": False}])):
        response = client.post(
            "/api/deck/generate-complete",
            json={
                "topic": "Quadratic Equations",
                "subject": "Mathematics",
                "gradeLevel": "10",
                "structuredFormat": True,
                "theme": "default",
                "pedagogyFlow": "problem_solving_math",
            },
        )

    assert response.status_code == 200, response.text
    assert planner_mock.call_args.kwargs["pedagogy_flow"] == "problem_solving_math"
    body = response.json()
    assert body["meta"]["pedagogical_flow"] == "problem_solving_math"
