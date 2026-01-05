from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    LessonPlanGenerateRequest,
    LessonPlanGenerateResponse,
    LessonStep,
    LessonStep,
    Concept
)
from app.models.modify_schemas import LessonPlanModifyRequest
from app.services.openai_service import generate_json_completion
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/generate-lesson-plan", response_model=LessonPlanGenerateResponse)
async def generate_lesson_plan(request: LessonPlanGenerateRequest):
    """Generate a complete lesson plan using AI"""
    try:
        # DEFENSIVE: Ensure all topics are strings and filter out empty ones
        topics_list = [str(topic) for topic in request.topics if topic]
        topics_str = ", ".join(topics_list)
        num_topics = len(topics_list)
        
        # Calculate time allocations using research-based lesson structure
        warmup_time = max(5, int(request.totalDuration * 0.10))  # 10% for engagement
        main_time = int(request.totalDuration * 0.70)  # 70% for core instruction
        closure_time = max(5, int(request.totalDuration * 0.15))  # 15% for closure
        assessment_time = request.totalDuration - warmup_time - main_time - closure_time
        
        system_message = """You are a master educator and curriculum specialist with expertise in backward design, differentiated instruction, and evidence-based teaching practices. You have deep knowledge of learning standards, cognitive science, and classroom management.

Your lesson plans are known for:
- Clear alignment between objectives, activities, and assessments
- Strategic scaffolding that builds student understanding
- Differentiation strategies for diverse learners
- Practical, classroom-tested activities and transitions
- Efficient use of instructional time
- Formative assessment opportunities throughout
- Resources that are realistic and accessible

You design lessons that are immediately implementable by any qualified teacher, with enough detail to ensure quality instruction while allowing for teacher autonomy and adaptation.

Always respond with valid, comprehensive JSON that follows professional lesson planning standards."""

        prompt = f"""Design a complete, professional-grade lesson plan using backward design principles.

LESSON SPECIFICATIONS:
- Topics to Cover: {topics_str}
- Subject Area: {request.subject}
- Grade Level: {request.gradeLevel}
- Total Duration: {request.totalDuration} minutes
- Number of Topics: {num_topics}

BACKWARD DESIGN FRAMEWORK:

STAGE 1: DESIRED RESULTS (What should students learn?)
Create 3-5 SMART learning objectives that:
- Start with measurable action verbs (Bloom's Taxonomy: analyze, evaluate, create, apply, etc.)
- Are specific to the topics: {topics_str}
- Are achievable within {request.totalDuration} minutes
- Target appropriate cognitive level for {request.gradeLevel}
- Connect to broader learning standards when relevant

Example format: "Students will be able to [action verb] [specific content] [context/criteria]"

STAGE 2: ASSESSMENT EVIDENCE (How will we know they learned?)
Design multiple assessment strategies:
- Formative assessments (2-3): Quick checks during lesson (exit tickets, questioning, observation)
- Summative assessment (1): End-of-lesson or follow-up assessment
- Include specific success criteria or rubric elements
- Make assessments directly measure the objectives

STAGE 3: LEARNING PLAN (How will we teach it?)

A. CONCEPT MAPPING:
Identify {num_topics * 2}-{num_topics * 3} key concepts across topics:
- Each concept needs: unique ID, clear name, concise description (1-2 sentences)
- Order concepts from foundational to advanced
- Connect concepts logically (prerequisites and dependencies)
- Include both content knowledge and skills

B. INSTRUCTIONAL SEQUENCE:
Design {max(5, num_topics + 3)}-{max(8, num_topics + 5)} instructional activities following this structure:

**Phase 1: ENGAGE & ACTIVATE (≈{warmup_time} min)**
- Opening activity that hooks students and activates prior knowledge
- Method: Quick discussion, KWL chart, provocative question, demonstration, etc.
- Clear learning intentions shared with students

**Phase 2: EXPLORE & EXPLAIN (≈{main_time} min total)**
- Break into {num_topics * 2}-{num_topics * 3} strategic activities covering all topics
- Include mix of teaching methods:
  * Direct instruction (mini-lectures, modeling, demonstrations)
  * Guided practice (scaffolded work with teacher support)
  * Collaborative learning (pair work, group activities)
  * Independent application
- Each activity should:
  * Have specific duration (ensure all durations sum to {request.totalDuration})
  * List concrete resources needed
  * Specify clear teaching method
  * Include transition notes if helpful
  * Address specific concept(s) from your concept map

**Phase 3: ELABORATE & APPLY (within main instruction)**
- Include at least one activity where students apply learning to new context
- Could be problem-solving, case study, creative application, or analysis

**Phase 4: EVALUATE & CLOSE (≈{closure_time + assessment_time} min)**
- Formative assessment activity
- Closure activity that synthesizes learning
- Preview of next lesson or homework

DIFFERENTIATION CONSIDERATIONS:
- Include at least one strategy for supporting struggling learners
- Include at least one extension for advanced learners
- Consider multiple entry points and learning modalities

RESOURCE REQUIREMENTS:
List 5-10 specific, realistic resources:
- Required materials (handouts, manipulatives, supplies)
- Technology needs (specific apps, websites, equipment)
- Reference materials (textbooks, articles, videos - be specific)
- Preparation items (pre-cut materials, pre-written prompts)

OUTPUT FORMAT (return as JSON):
{{
    "title": "Engaging, specific lesson title that captures the learning goal",
    "objectives": [
        "Students will be able to [specific, measurable objective 1 using action verb]",
        "Students will be able to [specific, measurable objective 2]",
        "Include 3-5 SMART objectives total"
    ],
    "concepts": [
        {{
            "id": "concept-1",
            "name": "First Key Concept",
            "description": "Clear 1-2 sentence explanation of this concept and why it matters"
        }},
        {{
            "id": "concept-2",
            "name": "Second Key Concept",
            "description": "Description connecting to previous concepts where relevant"
        }}
        // Include {num_topics * 2}-{num_topics * 3} concepts total
    ],
    "sequence": [
        {{
            "order": 1,
            "activity": "Engaging Hook: [Specific activity name and description]",
            "duration": {warmup_time},
            "method": "Discussion/Question prompt/Demonstration",
            "resources": ["Specific resource needed", "Another resource"],
            "notes": "[Optional: Transition tips, differentiation notes, key questions to ask]"
        }},
        {{
            "order": 2,
            "activity": "Direct Instruction: [Specific content - what exactly will be taught]",
            "duration": 15,
            "method": "Mini-lecture with visual aids",
            "resources": ["Presentation slides on [topic]", "Diagram/chart showing [concept]"],
            "concepts": ["concept-1", "concept-2"],
            "notes": "Check for understanding: Ask students to [specific check]"
        }}
        // Continue with {max(5, num_topics + 3)}-{max(8, num_topics + 5)} total activities
        // Ensure durations sum to exactly {request.totalDuration} minutes
        // Final activity should be closure/assessment
    ],
    "assessments": [
        "Formative: [Specific strategy - what will you do and what will you look for?]",
        "Formative: [Another ongoing check during lesson]",
        "Summative: [End assessment - specific task/assignment with success criteria]"
    ],
    "resources": [
        "[Specific resource 1 with details - not generic]",
        "[Specific resource 2 - include source if relevant]",
        "Include 5-10 concrete, obtainable resources"
    ],
    "differentiation": {{
        "support": "Strategy for struggling learners: [specific approach]",
        "extension": "Challenge for advanced learners: [specific approach]"
    }}
}}

QUALITY STANDARDS:
- All activities must explicitly connect to stated objectives
- Total duration of all sequence activities must equal {request.totalDuration} minutes
- Assessment methods must directly measure the objectives
- Include specific examples, not vague placeholders
- Resources must be realistic and specific (not "materials as needed")
- Transitions between activities should be logical and smooth
- Balance teacher-led and student-centered activities
- Include at least 3 different teaching methods
- Concepts should cover all topics: {topics_str}
- Everything should be appropriate for {request.gradeLevel} students

COHERENCE CHECK:
✓ Do objectives align with topics: {topics_str}?
✓ Do activities teach toward the objectives?
✓ Do assessments measure the objectives?
✓ Do concepts cover all necessary content?
✓ Does sequence flow logically and use time wisely?
✓ Are methods varied and age-appropriate?

Generate the complete lesson plan now. Make it detailed, professional, and immediately usable for classroom instruction."""

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=3500,  # Increased for comprehensive plans
            temperature=0.6   # Slightly lower for more structured output
        )

        # Transform and validate response
        concepts = [Concept(**c) for c in result["concepts"]]
        sequence = [LessonStep(**s) for s in result["sequence"]]
        
        # Validate timing adds up
        total_sequence_time = sum(step.duration for step in sequence)
        if abs(total_sequence_time - request.totalDuration) > 5:  # Allow 5 min variance
            print(f"Warning: Sequence duration ({total_sequence_time}) doesn't match requested ({request.totalDuration})")

        # Extract differentiation if present
        differentiation = result.get("differentiation", {})
        
        return LessonPlanGenerateResponse(
            title=result["title"],
            objectives=result["objectives"],
            concepts=concepts,
            sequence=sequence,
            assessments=result["assessments"],
            resources=result["resources"],
            differentiation=differentiation if differentiation else None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate lesson plan: {str(e)}")

@router.post("/modify-lesson-plan", response_model=LessonPlanGenerateResponse)
async def modify_lesson_plan(request: LessonPlanModifyRequest):
    """Modify an existing lesson plan based on user feedback"""
    try:
        import json
        current_plan_json = json.dumps(request.currentPlan, indent=2)
        
        system_message = """You are an expert curriculum specialist revising a lesson plan.
        Apply the user's feedback to the provided JSON lesson plan. 
        Maintain the strict JSON structure. Return the FULL updated plan."""

        prompt = f"""REVISE THIS LESSON PLAN.

        CONTEXT:
        Subject: {request.subject}
        Grade: {request.gradeLevel}

        USER FEEDBACK:
        "{request.feedback}"

        CURRENT PLAN JSON:
        {current_plan_json}

        OUTPUT FORMAT: Valid JSON matching the original schema (objectives, concepts, sequence, etc.).
        """

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=3500,
            temperature=0.6
        )

        # Transform and validate response
        concepts = [Concept(**c) for c in result.get("concepts", [])]
        sequence = [LessonStep(**s) for s in result.get("sequence", [])]
        
        differentiation = result.get("differentiation", {})

        return LessonPlanGenerateResponse(
            title=result.get("title", "Updated Lesson Plan"),
            objectives=result.get("objectives", []),
            concepts=concepts,
            sequence=sequence,
            assessments=result.get("assessments", []),
            resources=result.get("resources", []),
            differentiation=differentiation if differentiation else None
        )

    except Exception as e:
        logger.error(f"Lesson plan modification failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to modify lesson plan: {str(e)}")


@router.post("/generate-curriculum-plan")
async def generate_curriculum_plan(request_data: dict):
    """Generate a comprehensive curriculum plan with objectives and time estimates for each topic"""
    try:
        grade_level = request_data.get("gradeLevel", "")
        subject = request_data.get("subject", "")
        chapters = request_data.get("chapters", [])  # Full curriculum data from backend
        
        if not grade_level or not subject:
            raise HTTPException(status_code=400, detail="gradeLevel and subject are required")
        
        # Build chapter/topic list for prompt
        curriculum_text = ""
        for chapter in chapters:
            chapter_name = chapter.get("name", "")
            topics = chapter.get("topics", [])
            topic_names = [t.get("name", "") for t in topics]
            curriculum_text += f"\n**{chapter_name}**:\n"
            for t in topic_names:
                curriculum_text += f"  - {t}\n"
        
        system_message = """You are an expert curriculum planner with deep knowledge of educational standards, pedagogy, and classroom time management.

Your task is to analyze a curriculum and provide:
1. Clear learning objectives for each topic (2-3 measurable objectives using Bloom's taxonomy verbs)
2. Realistic time estimates based on topic complexity
3. Key teaching points that capture the essence of each topic

You understand that:
- One class period = 40-45 minutes
- Complex topics need more time
- Objectives should be SMART (Specific, Measurable, Achievable, Relevant, Time-bound)
- Key points should be memorable and concise

Always respond with valid JSON."""

        prompt = f"""Generate a comprehensive curriculum teaching plan.

CURRICULUM DETAILS:
- Grade Level: Class {grade_level}
- Subject: {subject}
- Curriculum Overview:
{curriculum_text}

For EACH topic in EACH chapter, generate:

1. **objectives** (2-3 learning objectives per topic):
   - Start with action verbs (Define, Explain, Calculate, Analyze, Compare, etc.)
   - Be specific to the topic content
   - Appropriate for Class {grade_level} students

2. **teachingMinutes** (estimated teaching time):
   - Simple concepts: 30-45 minutes (1 period)
   - Moderate concepts: 60-90 minutes (2 periods)
   - Complex concepts: 90-135 minutes (3 periods)
   - Very complex: 135-180 minutes (4 periods)

3. **periods** (number of class periods, 1 period = 45 min)

4. **keyPoints** (3-5 essential teaching points):
   - Core formulas, definitions, or principles
   - Common misconceptions to address
   - Important examples or applications

OUTPUT FORMAT (return as JSON):
{{
    "title": "Class {grade_level} {subject} - Complete Curriculum Plan",
    "subject": "{subject}",
    "gradeLevel": "{grade_level}",
    "totalHours": <calculated sum of all hours>,
    "totalPeriods": <calculated sum of all periods>,
    "chapters": [
        {{
            "name": "Chapter Name",
            "totalMinutes": <sum of topic minutes>,
            "totalPeriods": <sum of topic periods>,
            "topics": [
                {{
                    "name": "Topic Name",
                    "objectives": [
                        "Students will be able to define...",
                        "Students will be able to explain..."
                    ],
                    "teachingMinutes": 60,
                    "periods": 2,
                    "keyPoints": [
                        "Key formula or concept",
                        "Important application",
                        "Common mistake to avoid"
                    ]
                }}
            ]
        }}
    ]
}}

QUALITY STANDARDS:
- Every topic from the curriculum must be included
- Time estimates should be realistic for Class {grade_level}
- Objectives must be actionable and measurable
- Key points should enable quick lesson prep
- Total hours should reflect a typical academic year allocation

Generate the complete curriculum plan now."""

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=4000,
            temperature=0.6
        )
        
        # Validate and return
        return result

    except Exception as e:
        logger.error(f"Curriculum plan generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate curriculum plan: {str(e)}")
