from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    LessonPlanGenerateRequest,
    LessonPlanGenerateResponse,
    LessonStep,
    Concept,
    SessionIntroduction,
    CheckForUnderstanding,
    LessonSession,
    AssessmentPlan,
    DifferentiationPlan
)
from app.models.modify_schemas import LessonPlanModifyRequest
from app.services.openai_service import generate_json_completion
import logging
import math

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/generate-lesson-plan", response_model=LessonPlanGenerateResponse)
async def generate_lesson_plan(request: LessonPlanGenerateRequest):
    """Generate a complete multi-session lesson plan using AI"""
    try:
        # DEFENSIVE: Ensure all topics are strings and filter out empty ones
        topics_list = [str(topic) for topic in request.topics if topic]
        topics_str = ", ".join(topics_list)
        num_topics = len(topics_list)
        
        # Calculate number of sessions based on topic count
        # Rule: ~1-2 topics per session for thorough coverage
        class_duration = request.classDuration
        num_sessions = max(1, math.ceil(num_topics / 1.5))  # Avg 1.5 topics per session
        total_duration = num_sessions * class_duration  # Calculate total based on sessions
        
        # Calculate time allocations per session using research-based lesson structure
        intro_time = max(5, int(class_duration * 0.12))  # 12% for hook/intro
        main_time = int(class_duration * 0.65)  # 65% for core instruction (I Do, We Do, You Do)
        assessment_time = max(3, int(class_duration * 0.10))  # 10% for formative checks
        closure_time = max(5, int(class_duration * 0.13))  # 13% for closure
        
        system_message = """You are a master educator and curriculum specialist with expertise in backward design, differentiated instruction, and evidence-based teaching practices. You have deep knowledge of learning standards, cognitive science, and classroom management.

Your lesson plans are known for:
- Clear alignment between objectives, activities, and assessments
- Strategic scaffolding using "I Do, We Do, You Do" methodology
- Engaging hooks that capture student interest and activate prior knowledge
- Differentiation strategies for diverse learners (struggling, advanced, IEP/ELL)
- Practical, classroom-tested activities with smooth transitions
- Efficient use of instructional time with realistic pacing
- Formative assessment opportunities woven throughout
- Clear closure activities that synthesize learning

You design lessons that are immediately implementable by any qualified teacher, with enough detail to ensure quality instruction while allowing for teacher autonomy and adaptation.

Always respond with valid, comprehensive JSON that follows professional lesson planning standards."""

        prompt = f"""Design a complete, professional-grade MULTI-SESSION lesson plan using backward design principles.

LESSON SPECIFICATIONS:
- Topics to Cover: {topics_str}
- Subject Area: {request.subject}
- Grade Level: {request.gradeLevel}
- Class Period Duration: {class_duration} minutes per session
- Number of Sessions Needed: {num_sessions} (based on {num_topics} topics to cover thoroughly)
- Total Teaching Time: {total_duration} minutes

===== STAGE 1: DESIRED RESULTS (What should students learn?) =====

MASTER OBJECTIVES (for the entire unit):
Create 3-5 SMART learning objectives using the SWBAT (Students Will Be Able To) format:
- Start with measurable action verbs (Bloom's Taxonomy: analyze, evaluate, create, apply, compare, etc.)
- Specific to topics: {topics_str}
- Achievable within {num_sessions} class sessions
- Target appropriate cognitive level for {request.gradeLevel}

PREREQUISITES:
List 2-4 things students should already know before starting this lesson.

===== STAGE 2: ASSESSMENT EVIDENCE (How will we know they learned?) =====

FORMATIVE ASSESSMENTS (ongoing):
- Design 2-3 quick checks to use DURING instruction
- Examples: exit tickets, thumbs up/down, whiteboard responses, pair-share explains

SUMMATIVE ASSESSMENT (end):
- One comprehensive end-of-lesson/unit assessment
- Could be: quiz, project, presentation, written response

===== STAGE 3: LEARNING PLAN (How will we teach it?) =====

CONCEPT MAPPING:
Identify {max(3, num_topics * 2)} key concepts across topics:
- Each concept: unique ID, name, 1-2 sentence description
- Order from foundational to advanced

SESSION STRUCTURE (design {num_sessions} complete sessions):

For EACH of the {num_sessions} sessions, create:

**A. SESSION OBJECTIVES (2-3 per session)**
- Specific SWBAT statements for just that session
- Should build toward master objectives

**B. INTRODUCTION/HOOK (≈{intro_time} minutes)**
Design an engaging opener with:
- "hook": A thought-provoking question, short demo, video clip, surprising fact, or quick poll that captures attention
- "priorKnowledge": How you'll activate what students already know (KWL, quick discussion, review question)
- "agendaShare": Brief statement sharing today's learning target with students

**C. LEARNING ACTIVITIES (≈{main_time} minutes total)**
Use the "I Do, We Do, You Do" structure:

1. "I Do" (Teacher models): 
   - Direct instruction, demonstration, think-aloud
   - Teacher shows exactly how to do the skill/concept
   
2. "We Do" (Guided practice):
   - Students practice WITH teacher support
   - Pair work, whole-class problem-solving, guided examples
   
3. "You Do" (Independent practice):
   - Students work independently to demonstrate understanding
   - Can include collaborative work with minimal teacher help

Each activity must have:
- order (1, 2, 3...)
- activity (detailed description of what happens)
- duration (in minutes - MUST sum to session duration)
- method ("I Do", "We Do", "You Do", "Discussion", "Demonstration", etc.)
- resources (specific materials needed)
- notes (optional: key questions to ask, common mistakes to address)

**D. CHECK FOR UNDERSTANDING (≈{assessment_time} minutes)**
During and after activities, include 2-3 formative checks:
- type: "questioning", "quick_quiz", "whiteboard", "verbal_summary", "exit_ticket", etc.
- prompt: The specific question or task
- expectedResponse: What a successful response looks like (optional)

**E. CLOSURE (≈{closure_time} minutes)**
Synthesize learning:
- Quick summary of key points
- Connection to next session or real-world application
- Preview what's coming next (if not final session)

===== DIFFERENTIATION STRATEGIES =====

SUPPORT (for struggling learners):
- 2-3 specific strategies (simplified materials, extra scaffolding, peer tutoring)

EXTENSION (for advanced learners):
- 2-3 challenge activities (deeper questions, additional complexity, independent research)

ACCOMMODATIONS (for IEP/ELL students, optional):
- Visual aids, modified assignments, extra time, etc.

===== OUTPUT FORMAT (return as JSON) =====
{{
    "title": "Engaging, specific lesson title that captures the learning goal",
    "objectives": [
        "Students will be able to [master objective 1]",
        "Students will be able to [master objective 2]",
        "Students will be able to [master objective 3]"
    ],
    "prerequisites": [
        "Understanding of [prior concept 1]",
        "Ability to [prior skill]"
    ],
    "standards": ["Optional curriculum standard alignment"],
    "concepts": [
        {{
            "id": "concept-1",
            "name": "First Key Concept",
            "description": "Clear explanation of this concept"
        }}
    ],
    "sessions": [
        {{
            "sessionNumber": 1,
            "title": "Session 1: [Focus of this session]",
            "duration": {class_duration},
            "objectives": [
                "SWBAT [session-specific objective 1]",
                "SWBAT [session-specific objective 2]"
            ],
            "introduction": {{
                "hook": "Start with a surprising question: [specific question or activity]",
                "priorKnowledge": "Ask students to recall [specific prior knowledge activation]",
                "agendaShare": "Today we will learn to [learning target in student-friendly language]"
            }},
            "activities": [
                {{
                    "order": 1,
                    "activity": "I Do: Teacher demonstrates [specific skill/concept]",
                    "duration": 10,
                    "method": "I Do",
                    "resources": ["Whiteboard", "Example problems"],
                    "notes": "Key point to emphasize: [important note]"
                }},
                {{
                    "order": 2,
                    "activity": "We Do: Work through [specific practice] together",
                    "duration": 15,
                    "method": "We Do",
                    "resources": ["Student handout", "Guided practice worksheet"],
                    "notes": "Common mistake: [what to watch for]"
                }},
                {{
                    "order": 3,
                    "activity": "You Do: Students independently [specific task]",
                    "duration": 12,
                    "method": "You Do",
                    "resources": ["Independent practice sheet"],
                    "notes": "Circulate and provide individual feedback"
                }}
            ],
            "checkForUnderstanding": [
                {{
                    "type": "questioning",
                    "prompt": "Can someone explain [concept] in their own words?",
                    "expectedResponse": "Students should mention [key elements]"
                }},
                {{
                    "type": "whiteboard",
                    "prompt": "Solve this quick problem: [example]",
                    "expectedResponse": "Correct answer is [X]"
                }}
            ],
            "closure": "Today we learned [summary]. Tomorrow we will build on this by [preview]."
        }}
    ],
    "assessments": {{
        "formative": [
            "Quick check: [specific formative assessment strategy]",
            "Exit ticket: [specific question or prompt]"
        ],
        "summative": "End-of-unit quiz covering [topics] with [format description]"
    }},
    "resources": [
        "Specific resource 1 (with source if relevant)",
        "Specific resource 2",
        "Include 5-10 concrete, obtainable resources"
    ],
    "differentiation": {{
        "support": [
            "Provide graphic organizer for [concept]",
            "Pair struggling students with peer tutors"
        ],
        "extension": [
            "Challenge: Have students create their own [advanced task]",
            "Research: Explore [deeper topic]"
        ],
        "accommodations": [
            "Visual aids for ELL students",
            "Extended time for written responses"
        ]
    }},
    "totalSessions": {num_sessions},
    "totalDuration": {total_duration}
}}

===== QUALITY STANDARDS =====
✓ Each session's activity durations MUST sum to exactly {class_duration} minutes
✓ All activities connect to stated objectives
✓ Include at least one "I Do", "We Do", and "You Do" per session
✓ Formative checks are specific and actionable
✓ Resources are realistic and accessible
✓ Transitions between activities are logical
✓ Appropriate for {request.gradeLevel} students
✓ Covers all topics: {topics_str}

Generate the complete {num_sessions}-session lesson plan now. Make it detailed, professional, and immediately usable for classroom instruction."""

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=4000,  # Max supported by model
            temperature=0.6
        )

        # Transform and validate response
        concepts = [Concept(**c) for c in result.get("concepts", [])]
        
        sessions = []
        for s in result.get("sessions", []):
            intro = SessionIntroduction(**s.get("introduction", {}))
            activities = [LessonStep(**a) for a in s.get("activities", [])]
            checks = [CheckForUnderstanding(**c) for c in s.get("checkForUnderstanding", [])]
            
            session = LessonSession(
                sessionNumber=s.get("sessionNumber", 1),
                title=s.get("title", f"Session {s.get('sessionNumber', 1)}"),
                duration=s.get("duration", class_duration),
                objectives=s.get("objectives", []),
                introduction=intro,
                activities=activities,
                checkForUnderstanding=checks,
                closure=s.get("closure", "")
            )
            sessions.append(session)
        
        # Validate timing for each session
        for session in sessions:
            session_time = sum(step.duration for step in session.activities)
            if abs(session_time - session.duration) > 10:  # Allow 10 min variance
                logger.warning(f"Session {session.sessionNumber} duration mismatch: activities={session_time}, expected={session.duration}")

        # Build assessment plan
        assessments_data = result.get("assessments", {})
        assessments = AssessmentPlan(
            formative=assessments_data.get("formative", []),
            summative=assessments_data.get("summative", "End-of-lesson assessment")
        )
        
        # Build differentiation plan
        diff_data = result.get("differentiation", {})
        differentiation = DifferentiationPlan(
            support=diff_data.get("support", []),
            extension=diff_data.get("extension", []),
            accommodations=diff_data.get("accommodations")
        )
        
        return LessonPlanGenerateResponse(
            title=result.get("title", "Lesson Plan"),
            objectives=result.get("objectives", []),
            prerequisites=result.get("prerequisites", []),
            standards=result.get("standards"),
            concepts=concepts,
            sessions=sessions,
            assessments=assessments,
            resources=result.get("resources", []),
            differentiation=differentiation,
            totalSessions=len(sessions),
            totalDuration=sum(s.duration for s in sessions)
        )

    except Exception as e:
        logger.error(f"Lesson plan generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate lesson plan: {str(e)}")

@router.post("/modify-lesson-plan", response_model=LessonPlanGenerateResponse)
async def modify_lesson_plan(request: LessonPlanModifyRequest):
    """Modify an existing lesson plan based on user feedback"""
    try:
        import json
        current_plan_json = json.dumps(request.currentPlan, indent=2)
        
        system_message = """You are an expert curriculum specialist revising a multi-session lesson plan.
        Apply the user's feedback to the provided JSON lesson plan. 
        Maintain the strict JSON structure with sessions, activities, checkForUnderstanding, etc.
        Return the FULL updated plan with all sessions."""

        prompt = f"""REVISE THIS MULTI-SESSION LESSON PLAN.

        CONTEXT:
        Subject: {request.subject}
        Grade: {request.gradeLevel}

        USER FEEDBACK:
        "{request.feedback}"

        CURRENT PLAN JSON:
        {current_plan_json}

        OUTPUT FORMAT: Valid JSON matching the original schema with sessions, differentiation, assessments, etc.
        Preserve the multi-session structure.
        """

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=4000,
            temperature=0.6
        )

        # Transform and validate response
        concepts = [Concept(**c) for c in result.get("concepts", [])]
        
        sessions = []
        for s in result.get("sessions", []):
            intro = SessionIntroduction(**s.get("introduction", {}))
            activities = [LessonStep(**a) for a in s.get("activities", [])]
            checks = [CheckForUnderstanding(**c) for c in s.get("checkForUnderstanding", [])]
            
            session = LessonSession(
                sessionNumber=s.get("sessionNumber", 1),
                title=s.get("title", f"Session {s.get('sessionNumber', 1)}"),
                duration=s.get("duration", 45),
                objectives=s.get("objectives", []),
                introduction=intro,
                activities=activities,
                checkForUnderstanding=checks,
                closure=s.get("closure", "")
            )
            sessions.append(session)

        # Build assessment plan
        assessments_data = result.get("assessments", {})
        assessments = AssessmentPlan(
            formative=assessments_data.get("formative", []),
            summative=assessments_data.get("summative", "End-of-lesson assessment")
        )
        
        # Build differentiation plan
        diff_data = result.get("differentiation", {})
        differentiation = DifferentiationPlan(
            support=diff_data.get("support", []),
            extension=diff_data.get("extension", []),
            accommodations=diff_data.get("accommodations")
        )

        return LessonPlanGenerateResponse(
            title=result.get("title", "Updated Lesson Plan"),
            objectives=result.get("objectives", []),
            prerequisites=result.get("prerequisites", []),
            standards=result.get("standards"),
            concepts=concepts,
            sessions=sessions,
            assessments=assessments,
            resources=result.get("resources", []),
            differentiation=differentiation,
            totalSessions=len(sessions),
            totalDuration=sum(s.duration for s in sessions)
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
        additional_instructions = request_data.get("additionalInstructions", "")  # Teacher's custom instructions
        
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

        # Add teacher's additional instructions if provided
        if additional_instructions:
            prompt += f"""

ADDITIONAL TEACHER INSTRUCTIONS:
{additional_instructions}

Please incorporate these instructions into your curriculum plan.
"""

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
