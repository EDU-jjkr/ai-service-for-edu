import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import asyncio

from app.agents.visual_director_agent import VisualDirectorAgent
from app.models.lesson_schema import BloomLevel, SlideType
from app.services.curated_assets import lookup_curated_asset
from app.services.stock_photo_service import StockPhotoService


def test_returns_curated_asset_for_known_science_concept():
    asset = lookup_curated_asset(
        subject="Biology",
        topic="Photosynthesis",
        pedagogical_role="explain_core",
    )

    assert asset is not None
    assert asset.asset_type == "diagram"
    assert "photosynthesis" in asset.asset_id


def test_returns_none_for_unknown_topic():
    asset = lookup_curated_asset(
        subject="History",
        topic="Local Trade Routes",
        pedagogical_role="hook",
    )

    assert asset is None


def test_visual_director_prefers_curated_asset_before_llm_generation(monkeypatch):
    async def fail_if_called(**kwargs):
        raise AssertionError("LLM fallback should not be used when a curated asset exists")

    monkeypatch.setattr(
        "app.agents.visual_director_agent.generate_json_completion",
        fail_if_called,
    )

    result = asyncio.run(
        VisualDirectorAgent.generate_image_query(
            slide_content="Plants use sunlight to convert carbon dioxide and water into glucose.",
            slide_title="Photosynthesis",
            bloom_level=BloomLevel.UNDERSTAND,
            subject="Biology",
            grade_level="8",
            slide_type=SlideType.CONCEPT,
        )
    )

    assert result["imageType"] == "diagram"
    assert result["orientation"] == "landscape"
    assert result["confidence"] == 95
    assert result["imageQuery"].startswith("curated://")
    assert "chloroplast" in result["imageQuery"].lower()


def test_stock_photo_service_skips_weak_quantitative_stock_fallback():
    service = StockPhotoService()

    result = asyncio.run(service.fetch_image("students studying math in classroom", subject="Mathematics"))

    assert result == (None, None)


def test_stock_photo_service_skips_provider_fetches_for_curated_marker(monkeypatch):
    service = StockPhotoService()
    provider_calls = {"unsplash": 0, "pexels": 0}

    async def unsplash_called(*args, **kwargs):
        provider_calls["unsplash"] += 1
        raise AssertionError("Unsplash provider should not be called for curated markers")

    async def pexels_called(*args, **kwargs):
        provider_calls["pexels"] += 1
        raise AssertionError("Pexels provider should not be called for curated markers")

    monkeypatch.setattr(service, "_fetch_from_unsplash", unsplash_called)
    monkeypatch.setattr(service, "_fetch_from_pexels", pexels_called)

    image_stream, attribution = asyncio.run(
        service.fetch_image(
            "curated://biology/photosynthesis/core-diagram|Use a labeled chloroplast and input/output arrows.",
            subject="Biology",
        )
    )

    assert provider_calls == {"unsplash": 0, "pexels": 0}
    assert image_stream is not None
    assert image_stream.getbuffer().nbytes > 0
    assert attribution is not None
    assert "curated" in attribution.lower()
    assert "photosynthesis process diagram" in attribution.lower()
