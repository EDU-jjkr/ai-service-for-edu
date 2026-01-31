from fastapi import APIRouter, HTTPException
from app.models.schemas import QuizGenerateRequest, QuizGenerateResponse
from app.services.openai_service import generate_json_completion

router = APIRouter()

@router.post("/generate-activity", response_model=QuizGenerateResponse)
async def generate_quiz(request: QuizGenerateRequest):
    """Generate interactive quiz questions"""
    try:
        # DEFENSIVE: Ensure all string fields are actually strings
        topic = str(request.topic) if request.topic else ""
        subject = str(request.subject) if request.subject else ""
        classLevel = str(request.classLevel) if request.classLevel else ""
        chapter = str(request.chapter) if request.chapter else ""
        count = int(request.count) if request.count else 5
        additional_instructions = str(request.additionalInstructions) if request.additionalInstructions else ""
        
        system_message = """You are an expert educational content creator specializing in interactive quizzes. 
You create engaging, curriculum-aligned questions that test understanding and critical thinking.
Your output must be strictly valid JSON."""

        prompt = f"""Generate {count} interactive quiz questions for the following context:
- Subject: {subject}
- Class/Grade: {classLevel}
- Chapter: {chapter}
- Topic: {topic}

Requirements:
1. Questions should be relevant to the specific topic and chapter.
2. Mix of types: 'multiple-choice' (mostly), 'true-false', or 'short-answer'.
3. For multiple-choice, provide exactly 4 options.
4. Difficulty Progression:
   - Start with 'easy' questions (conceptual/basic).
   - Move to 'medium' questions (application-based).
   - End with 'hard' questions (complex/critical thinking).
5. For 'hard' questions:
   - The options must be VERY confusing and plausible.
   - Distractors should test deep understanding.
6. 'answer' must be the exact string of the correct option.
7. 'explanation' must explain WHY the answer is correct.
"""

        # Add teacher's additional instructions if provided
        if additional_instructions:
            prompt += f"""
ADDITIONAL TEACHER INSTRUCTIONS:
{additional_instructions}

Please incorporate these instructions into your question generation.
"""

        prompt += """
OUTPUT JSON FORMAT:
{{
    "questions": [
        {{
            "content": "Question text here?",
            "type": "multiple-choice",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer": "Option B",
            "explanation": "Explanation here...",
            "difficulty": "easy" 
        }}
    ]
}}
"""

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=2000,
            temperature=0.7
        )

        return QuizGenerateResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate quiz: {str(e)}")