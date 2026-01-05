from fastapi import APIRouter, HTTPException
from app.models.schemas import ActivityGenerateRequest, ActivityGenerateResponse
from app.services.openai_service import generate_json_completion

router = APIRouter()

@router.post("/generate-activity", response_model=ActivityGenerateResponse)
async def generate_activity(request: ActivityGenerateRequest):
    """Generate a classroom activity using AI"""
    try:
        # DEFENSIVE: Ensure all string fields are actually strings
        topic = str(request.topic) if request.topic else ""
        subject = str(request.subject) if request.subject else ""
        gradeLevel = str(request.gradeLevel) if request.gradeLevel else ""
        activityType = str(request.activityType) if request.activityType else ""
        duration = int(request.duration) if request.duration else 30
        
        # Enhanced system message with clear role and expertise
        system_message = """You are an award-winning educator with 15+ years of experience designing classroom activities across all grade levels and subjects. You specialize in creating engaging, hands-on learning experiences that cater to diverse learning styles and abilities.

Your activities are known for:
- Clear, actionable instructions that any teacher can follow
- Realistic material requirements available in typical classrooms
- Built-in differentiation strategies
- Strong alignment with learning standards
- Student engagement and active participation

You always respond with valid, well-structured JSON that teachers can immediately implement."""

        # Improved prompt with more context and structure
        prompt = f"""Design a comprehensive classroom activity based on the following specifications:

ACTIVITY PARAMETERS:
- Topic: "{topic}"
- Subject: {subject}
- Grade Level: {gradeLevel}
- Duration: {duration} minutes
- Activity Type: {activityType}

DESIGN REQUIREMENTS:

1. AGE APPROPRIATENESS:
   - Match cognitive abilities of {request.gradeLevel} students
   - Use vocabulary and concepts suitable for this age group
   - Consider attention span typical for this grade level

2. LEARNING DESIGN:
   - Begin with clear learning objectives
   - Include active learning elements
   - Incorporate multiple learning modalities (visual, auditory, kinesthetic)
   - Build from simple to complex concepts

3. PRACTICAL CONSIDERATIONS:
   - Materials should be readily available or easily substituted
   - Steps should be clear enough for a substitute teacher to follow
   - Include approximate time for each major step
   - Consider classroom management needs

4. ENGAGEMENT FACTORS:
   - Make it interactive and student-centered
   - Include collaboration opportunities if appropriate
   - Add elements of choice or creativity where possible

5. ASSESSMENT:
   - Include observable learning outcomes
   - Suggest quick formative assessment methods

OUTPUT FORMAT (return as JSON):
{{
    "title": "Compelling, descriptive activity title (not generic)",
    "materials": [
        "Specific material 1 with quantity if needed",
        "Material 2 with any preparation notes",
        "List 5-10 items; mark optional items with '(optional)'"
    ],
    "steps": [
        "Introduction/Hook (2-3 min): Specific engaging opening",
        "Step 2 with timing: Clear action with expected outcome",
        "Continue with 5-8 detailed steps",
        "Conclusion/Reflection (last step): How to wrap up and assess"
    ],
    "learningOutcomes": [
        "Students will be able to [specific, measurable action verb] [what they'll learn]",
        "Include 3-5 outcomes using Bloom's taxonomy action verbs",
        "Make outcomes specific to the topic, not generic"
    ]
}}

CRITICAL REQUIREMENTS:
- Ensure activity is realistically completable in {duration} minutes
- All materials must be safe and age-appropriate
- Steps must be numbered/sequenced logically
- Include timing estimates within steps
- Use active, clear language
- Avoid educational jargon; write for clarity

Generate the activity now. Be specific, practical, and creative."""

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=3000,
            temperature=0.7
        )

        return ActivityGenerateResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate activity: {str(e)}")