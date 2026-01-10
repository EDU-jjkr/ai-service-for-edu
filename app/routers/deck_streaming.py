from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import DeckGenerateRequest
from app.agents.deck_agents import OutlinerAgent, ContentAgent
import json
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-deck-advanced")
async def generate_deck_stream(request: DeckGenerateRequest):
    """
    Advanced Chain-of-Thought Deck Generation with Streaming.
    1. Outliner Agent -> Creates structure
    2. Content Agent -> Streams content for each slide sequentially (or parallel in future)
    """
    
    async def event_stream():
        try:
            # Step 1: Outlining
            yield json.dumps({"type": "status", "message": "Creating outline..."}) + "\n"
            
            topics_str = ", ".join(request.topics) if request.topics else request.topic
            outline = await OutlinerAgent.create_outline(
                topic=topics_str,
                subject=request.subject,
                grade_level=request.gradeLevel
            )
            
            yield json.dumps({"type": "outline", "data": outline}) + "\n"
            
            # Step 2: Content Generation
            # Ideally we run these in parallel, but for streaming to the client we might want sequential delivery 
            # so the client can render Slide 1, then Slide 2, etc.
            
            for i, slide_plan in enumerate(outline):
                yield json.dumps({"type": "status", "message": f"Generating slide {i+1}..."}) + "\n"
                
                # Verify slide_plan structure for ContentAgent
                if 'title' not in slide_plan or 'type' not in slide_plan:
                    continue

                full_content = ""
                # Start a new slide event
                yield json.dumps({
                    "type": "slide_start", 
                    "index": i, 
                    "title": slide_plan['title'],
                    "slideType": slide_plan.get('type')
                }) + "\n"
                
                # Stream the content chunks
                async for chunk in ContentAgent.generate_slide_content(
                    slide_outline=slide_plan,
                    subject=request.subject,
                    grade_level=request.gradeLevel
                ):
                    full_content += chunk
                    yield json.dumps({
                        "type": "slide_chunk", 
                        "index": i, 
                        "chunk": chunk
                    }) + "\n"
                
                yield json.dumps({
                    "type": "slide_end", 
                    "index": i,
                    "fullContent": full_content
                }) + "\n"

            yield json.dumps({"type": "status", "message": "Generation complete"}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
