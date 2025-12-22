from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.openai_service import generate_json_completion
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class TextbookIndexParseRequest(BaseModel):
    rawText: str
    subject: Optional[str] = None
    gradeLevel: Optional[str] = None

class TopicNode(BaseModel):
    id: str
    name: str
    subtopics: List['TopicNode'] = []
    pageNumber: Optional[str] = None

TopicNode.update_forward_refs()

class TextbookIndexParseResponse(BaseModel):
    chapters: List[TopicNode]

@router.post("/parse-index", response_model=TextbookIndexParseResponse)
async def parse_textbook_index(request: TextbookIndexParseRequest):
    """
    Parse a raw textbook index (text) into a structured hierarchy of topics.
    Useful for creating a lesson plan foundation for classes without a standard syllabus (e.g., < Class 8).
    """
    try:
        logger.info(f"Parsing textbook index for subject: {request.subject}, Grade: {request.gradeLevel}")

        system_message = """You are an expert educational content structurer. Your task is to take raw text from a textbook's table of contents or index and convert it into a clean, structured JSON hierarchy.

        Input might be unstructured, contain page numbers, dots, or OCR noise.
        
        Your Goal:
        1. Identify the high-level Chapters/Units.
        2. Identify specific Topics/Sections under each Chapter.
        3. Ignore irrelevant text (authors, prefaces, etc.) unless they are instructional units.
        4. Preserve logical ordering.
        """

        prompt = f"""Parse the following Textbook Index content into a hierarchical structure.

        CONTEXT:
        Subject: {request.subject or "Generla"}
        Grade: {request.gradeLevel or "Unknown"}

        RAW INDEX CONTENT:
        {request.rawText}

        OUTPUT FORMAT (JSON):
        {{
            "chapters": [
                {{
                    "id": "ch-1",
                    "name": "Chapter 1: Title",
                    "pageNumber": "1",
                    "subtopics": [
                        {{ "id": "ch-1-1", "name": "1.1 Topic Name", "pageNumber": "2" }},
                        {{ "id": "ch-1-2", "name": "1.2 Topic Name", "pageNumber": "5" }}
                    ]
                }}
            ]
        }}
        """

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=2000,
            temperature=0.3
        )

        return TextbookIndexParseResponse(chapters=result["chapters"])

    except Exception as e:
        logger.error(f"Failed to parse textbook index: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to parse index: {str(e)}")
