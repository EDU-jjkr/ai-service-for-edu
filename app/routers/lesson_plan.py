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
    DifferentiationPlan,
    ChunkBlock,
    ReflectionPrompts,
)
from app.models.modify_schemas import LessonPlanModifyRequest
from app.services.openai_service import generate_json_completion
from pydantic import ValidationError
import logging
import re

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------- CONSTANTS ----------

BANNED_VAGUE_VERBS = [
    "understand", "understands", "understanding",
    "know", "knows", "knowledge of",
    "learn", "learns", "learning about",
    "appreciate", "appreciates",
    "be aware of", "be familiar with", "grasp the concept",
]

MAX_GENERATION_ATTEMPTS = 2


# ---------- HELPERS ----------

def attention_span_minutes(grade_level: str) -> int:
    """Return a realistic single-chunk teaching span in minutes based on grade band.

    Guideline used: primary ~12 min, middle ~17 min, senior ~22 min.
    Falls back to middle-band if grade can't be parsed.
    """
    match = re.search(r"\d+", grade_level or "")
    grade_num = int(match.group()) if match else 6

    if grade_num <= 5:
        return 12
    elif grade_num <= 8:
        return 17
    else:
        return 22


def build_chunk_plan(main_time: int, grade_level: str) -> list[dict]:
    """Split the core-instruction time into attention-span-sized chunks.

    Each chunk gets a placeholder focus/checkIn the model is expected to
    fill in via the prompt instructions — this function just fixes the
    TIMING so the model can't default back to one long block.
    """
    span = attention_span_minutes(grade_level)
    if main_time <= span:
        return [{"order": 1, "duration": main_time}]

    num_chunks = max(2, round(main_time / span))
    base = main_time // num_chunks
    remainder = main_time - base * num_chunks

    chunks = []
    for i in range(num_chunks):
        duration = base + (1 if i < remainder else 0)
        chunks.append({"order": i + 1, "duration": duration})
    return chunks


def contains_vague_objective(objectives: list[str]) -> bool:
    text = " ".join(objectives).lower()
    return any(verb in text for verb in BANNED_VAGUE_VERBS)


def normalize_activity_durations(activities: list[LessonStep], target_duration: int) -> None:
    """Rescale activity durations in place so they sum exactly to target_duration.

    Proportional rescale + integer rounding, with any leftover minute(s)
    assigned to the longest activity so the total is always exact.
    """
    if not activities:
        return
    current_total = sum(a.duration for a in activities)
    if current_total == 0 or current_total == target_duration:
        return

    scale = target_duration / current_total
    scaled = [max(1, round(a.duration * scale)) for a in activities]

    diff = target_duration - sum(scaled)
    if diff != 0:
        longest_idx = max(range(len(scaled)), key=lambda i: scaled[i])
        scaled[longest_idx] += diff
        scaled[longest_idx] = max(1, scaled[longest_idx])

    for activity, new_duration in zip(activities, scaled):
        activity.duration = new_duration


def parse_sessions(raw_sessions: list[dict], class_duration: int) -> list[LessonSession]:
    sessions = []
    for s in raw_sessions:
        intro = SessionIntroduction(**s.get("introduction", {}))
        activities = [LessonStep(**a) for a in s.get("activities", [])]
        checks = [CheckForUnderstanding(**c) for c in s.get("checkForUnderstanding", [])]
        chunk_plan = [ChunkBlock(**c) for c in s.get("chunkPlan", [])]

        session_duration = s.get("duration", class_duration)
        normalize_activity_durations(activities, session_duration)

        session = LessonSession(
            sessionNumber=s.get("sessionNumber", 1),
            title=s.get("title", f"Session {s.get('sessionNumber', 1)}"),
            duration=session_duration,
            objectives=s.get("objectives", []),
            introduction=intro,
            activities=activities,
            checkForUnderstanding=checks,
            closure=s.get("closure", ""),
            chunkPlan=chunk_plan,
            backupPlan=s.get("backupPlan"),
        )
        sessions.append(session)
    return sessions


def build_prompt(request: LessonPlanGenerateRequest) -> tuple[str, str, dict]:
    """Builds the system message, main prompt, and timing metadata."""
    topics_list = [topic.name for topic in request.topics if topic.name]
    topics_str = ", ".join(topics_list)
    num_topics = len(topics_list)

    num_sessions = sum(topic.periodsRequired for topic in request.topics) or 1
    class_duration = request.classDuration
    total_duration = num_sessions * class_duration

    all_objectives = []
    all_concepts = []
    for t in request.topics:
        all_objectives.extend(t.learningObjectives)
        all_concepts.extend(t.keyConcepts)

    objectives_str = "\n".join(f"- {obj}" for obj in all_objectives)
    concepts_str = "\n".join(f"- {c}" for c in all_concepts)

    intro_time = max(5, int(class_duration * 0.12))
    main_time = int(class_duration * 0.65)
    assessment_time = max(3, int(class_duration * 0.10))
    closure_time = max(5, int(class_duration * 0.13))

    span = attention_span_minutes(request.gradeLevel)
    chunk_plan = build_chunk_plan(main_time, request.gradeLevel)
    chunk_count = len(chunk_plan)

    system_message = """You are a master educator and curriculum specialist with expertise in
backward design, cognitive load management, and evidence-based teaching practices.

Your core operating principle: a lesson plan exists to answer ONE question —
"how will THIS group of students learn THIS topic today?" — not "how much
content can I finish." You never optimize for content coverage over
comprehension.

You follow these non-negotiable rules:
- Every objective is a measurable action (solve, compare, identify, construct,
  critique, design...). You NEVER write objectives using "understand", "know",
  "learn about", or "be aware of" — these are unmeasurable and banned.
- One session, one primary objective. Supporting objectives are fine, but
  never stack multiple unrelated learning goals into a single session.
- Long explanation blocks are broken into short chunks matched to realistic
  attention spans, each ending in a quick, specific check-in — never a single
  unbroken lecture block.
- Hooks are genuine curiosity triggers (a question, an odd object, a
  surprising fact) — never "open your books to page X."
- Examples are grounded in things students actually encounter (money, sport,
  food, phones, weather) rather than abstract filler.
- Homework is small and purposeful (aim for ~5 meaningful items), never bulk
  repetition.
- You always include a concrete backup plan for when technology fails or
  timing runs short/long — because it eventually will.

Always respond with valid, comprehensive JSON only — no prose outside the
JSON structure."""

    prompt = f"""Design a complete, professional-grade MULTI-SESSION lesson plan using backward design principles.

LESSON SPECIFICATIONS:
- Topics to Cover: {topics_str}
- Subject Area: {request.subject}
- Grade Level: {request.gradeLevel}
- Class Period Duration: {class_duration} minutes per session
- Number of Sessions Needed: {num_sessions} (based on {num_topics} topics to cover thoroughly)
- Total Teaching Time: {total_duration} minutes
- Realistic attention span for this grade band: ~{span} minutes per instructional chunk

===== STAGE 1: DESIRED RESULTS =====

MASTER OBJECTIVES — use exactly these pre-approved curriculum objectives, do not invent new ones:
{objectives_str}

Each SESSION should organize around ONE primary objective drawn from the above list.
If a session's objective can be phrased with "understand" or "know", REWRITE it as
a measurable action instead (e.g. not "understand fractions" but "compare fractions
with unlike denominators and solve at least 8/10 practice items correctly").

PREREQUISITES: List 2-4 things students should already know before starting.

===== STAGE 2: ASSESSMENT EVIDENCE =====

FORMATIVE (ongoing, 2-3 quick checks used DURING instruction — exit tickets,
thumbs up/down, whiteboard response, pair-share).

SUMMATIVE (one comprehensive end-of-lesson/unit assessment).

===== STAGE 3: LEARNING PLAN =====

CONCEPT MAPPING — organize these pre-approved key concepts foundational-to-advanced:
{concepts_str}
Each concept: unique id, name, 1-2 sentence description.

SESSION STRUCTURE — design {num_sessions} complete sessions. For EACH session:

**A. SESSION OBJECTIVE** — one primary SWBAT statement (measurable verb, no
banned words), optionally 1 supporting objective.

**B. INTRODUCTION/HOOK (~{intro_time} min)**
- "hook": a specific curiosity trigger (question, object, surprising fact, short demo)
- "priorKnowledge": how you'll surface what students already know
- "agendaShare": the learning target in plain student-facing language

**C. CHUNKED CORE INSTRUCTION (~{main_time} min total, split into {chunk_count} chunks)**
This session needs a "chunkPlan" array with exactly {chunk_count} entries. The
durations are fixed below — you fill in "focus" (what slice of the objective
this chunk teaches) and "checkIn" (the specific quick question/signal that
ends the chunk, e.g. "thumbs up/down on whether X makes sense", "cold-call one
student to restate Y"):
{chunk_plan}
Do not merge these into one long explanation — each chunk should feel like a
distinct explain -> example -> quick-check unit ("I do" material lives here).

**D. GUIDED + INDEPENDENT PRACTICE (folds into "activities" alongside the I Do
chunks above)** — use "We Do" then "You Do":
- "We Do": students practice WITH support (pair work, guided problems)
- "You Do": students work independently to demonstrate understanding
Include for at least the "You Do" activity a "difficultyNote" describing how
the SAME task scales down for struggling learners and up for advanced ones
(e.g. "Support: 2 fewer steps, denominators pre-matched. Extension: add a
mixed-number case.").
Give each activity: order, activity, duration, method, resources, notes,
optional checkInPrompt, optional difficultyNote.
All activity durations (chunk + practice combined) must sum to exactly
{class_duration} minutes.

**E. CHECK FOR UNDERSTANDING (~{assessment_time} min)** — 2-3 formative checks:
type, prompt, expectedResponse (optional).

**F. CLOSURE (~{closure_time} min)** — summary of key points + one reflection
question put back to students ("tell me one thing you learned today") +
preview of next session if applicable.

**G. BACKUP PLAN** — one sentence: what to do if the tech fails, or this
topic clearly needs more/less time than planned.

===== DIFFERENTIATION (unit-level) =====
- support: 2-3 strategies for struggling learners
- extension: 2-3 strategies for advanced learners
- accommodations (optional): IEP/ELL specifics

===== POST-LESSON REFLECTION =====
Generate a "reflectionPrompts" object anticipating (for the teacher to check
after teaching): the point most likely to confuse students, which planned
explanation is likely strongest, which question is likely to spark the most
discussion, a question to verify the objective actually landed, and a prompt
for what to change next time.

===== OUTPUT FORMAT (JSON) =====
{{
    "title": "...",
    "objectives": ["Students will be able to [measurable action]..."],
    "prerequisites": ["..."],
    "standards": ["optional"],
    "concepts": [{{"id": "concept-1", "name": "...", "description": "..."}}],
    "sessions": [
        {{
            "sessionNumber": 1,
            "title": "...",
            "duration": {class_duration},
            "objectives": ["SWBAT ... (measurable, no banned verbs)"],
            "introduction": {{"hook": "...", "priorKnowledge": "...", "agendaShare": "..."}},
            "chunkPlan": [
                {{"order": 1, "focus": "...", "duration": <int>, "checkIn": "..."}}
            ],
            "activities": [
                {{
                    "order": 1,
                    "activity": "I Do: ...",
                    "duration": <int>,
                    "method": "I Do",
                    "resources": ["..."],
                    "notes": "...",
                    "checkInPrompt": "..."
                }},
                {{
                    "order": 2,
                    "activity": "We Do: ...",
                    "duration": <int>,
                    "method": "We Do",
                    "resources": ["..."],
                    "notes": "..."
                }},
                {{
                    "order": 3,
                    "activity": "You Do: ...",
                    "duration": <int>,
                    "method": "You Do",
                    "resources": ["..."],
                    "difficultyNote": "Support: ... Extension: ..."
                }}
            ],
            "checkForUnderstanding": [
                {{"type": "questioning", "prompt": "...", "expectedResponse": "..."}}
            ],
            "closure": "...",
            "backupPlan": "..."
        }}
    ],
    "assessments": {{"formative": ["..."], "summative": "..."}},
    "resources": ["5-10 concrete, obtainable resources"],
    "differentiation": {{"support": ["..."], "extension": ["..."], "accommodations": ["..."]}},
    "reflectionPrompts": {{
        "mostConfusingPoint": "...",
        "strongestExplanation": "...",
        "likelyDiscussionSpark": "...",
        "objectiveCheckQuestion": "...",
        "suggestedRevision": "..."
    }},
    "totalSessions": {num_sessions},
    "totalDuration": {total_duration}
}}

===== QUALITY STANDARDS =====
✓ NO objective anywhere uses "understand", "know", "learn about", "be aware of"
✓ Each session activity durations sum to EXACTLY {class_duration} minutes
✓ Core instruction is chunked into {chunk_count} pieces per session, never one block
✓ At least one "I Do", "We Do", "You Do" per session
✓ Hooks are specific curiosity triggers, never "open your book to page X"
✓ Homework/practice stays small and purposeful, never bulk repetition
✓ Every session has a backupPlan
✓ Appropriate for {request.gradeLevel} students
✓ Covers all topics: {topics_str}

Generate the complete {num_sessions}-session lesson plan now."""

    timing = {
        "num_sessions": num_sessions,
        "class_duration": class_duration,
        "total_duration": total_duration,
    }
    return system_message, prompt, timing


async def generate_and_validate(system_message: str, prompt: str, class_duration: int) -> dict:
    """Calls the LLM, validates against Pydantic models, retries once on failure,
    and runs a targeted re-prompt if banned vague verbs slip into objectives."""
    last_error = None
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        try:
            result = await generate_json_completion(
                prompt=prompt,
                system_message=system_message,
                max_tokens=32768,
                temperature=0.6,
            )

            # Validate shape early so we fail fast and retry rather than
            # discovering a broken field deep in the response-building code.
            _ = parse_sessions(result.get("sessions", []), class_duration)

            # Targeted fix for vague objectives instead of a full regeneration.
            all_objs = list(result.get("objectives", []))
            for s in result.get("sessions", []):
                all_objs.extend(s.get("objectives", []))

            if contains_vague_objective(all_objs):
                logger.info("Vague objective detected, requesting targeted rewrite")
                fix_prompt = f"""The following learning objectives use vague,
unmeasurable verbs (understand/know/learn about/be aware of). Rewrite ONLY
these into measurable actions (compare, solve, construct, critique, design,
identify, explain-with-example, etc.), keeping the same topic and meaning.

Objectives to fix:
{all_objs}

Return ONLY a JSON array of the rewritten objectives, in the same order,
same length, nothing else."""
                fixed = await generate_json_completion(
                    prompt=fix_prompt,
                    system_message="You rewrite vague learning objectives into measurable ones. Respond with a JSON array only.",
                    max_tokens=800,
                    temperature=0.3,
                )
                if isinstance(fixed, list) and len(fixed) == len(all_objs):
                    fixed_iter = iter(fixed)
                    result["objectives"] = [next(fixed_iter) for _ in result.get("objectives", [])]
                    for s in result.get("sessions", []):
                        s["objectives"] = [next(fixed_iter) for _ in s.get("objectives", [])]
                else:
                    logger.warning("Objective rewrite response shape mismatch, keeping originals")

            return result

        except (ValidationError, KeyError, TypeError) as e:
            last_error = e
            logger.warning(f"Generation attempt {attempt} failed validation: {e}")

    raise HTTPException(
        status_code=500,
        detail=f"Failed to generate a valid lesson plan after {MAX_GENERATION_ATTEMPTS} attempts: {last_error}",
    )


# ---------- ROUTES ----------

@router.post("/generate-lesson-plan", response_model=LessonPlanGenerateResponse)
async def generate_lesson_plan(request: LessonPlanGenerateRequest):
    """Generate a complete multi-session lesson plan using AI."""
    try:
        system_message, prompt, timing = build_prompt(request)
        result = await generate_and_validate(system_message, prompt, timing["class_duration"])

        concepts = [Concept(**c) for c in result.get("concepts", [])]
        sessions = parse_sessions(result.get("sessions", []), timing["class_duration"])

        assessments_data = result.get("assessments", {})
        assessments = AssessmentPlan(
            formative=assessments_data.get("formative", []),
            summative=assessments_data.get("summative", "End-of-lesson assessment"),
        )

        diff_data = result.get("differentiation", {})
        differentiation = DifferentiationPlan(
            support=diff_data.get("support", []),
            extension=diff_data.get("extension", []),
            accommodations=diff_data.get("accommodations"),
        )

        reflection_data = result.get("reflectionPrompts")
        reflection = ReflectionPrompts(**reflection_data) if reflection_data else None

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
            reflectionPrompts=reflection,
            totalSessions=len(sessions),
            totalDuration=sum(s.duration for s in sessions),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lesson plan generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate lesson plan: {str(e)}")


@router.post("/modify-lesson-plan", response_model=LessonPlanGenerateResponse)
async def modify_lesson_plan(request: LessonPlanModifyRequest):
    """Modify an existing lesson plan based on user feedback."""
    try:
        import json
        current_plan_json = json.dumps(request.currentPlan, indent=2)

        system_message = """You are an expert curriculum specialist revising a multi-session
lesson plan. Apply the user's feedback to the provided JSON lesson plan while
preserving every quality rule the plan was originally built with: measurable
objectives only (no "understand/know/learn about"), chunked instruction
matched to attention span, exact activity-duration sums, a backupPlan per
session, and a reflectionPrompts object. Maintain the strict JSON structure.
Return the FULL updated plan with all sessions."""

        prompt = f"""REVISE THIS MULTI-SESSION LESSON PLAN.

CONTEXT:
Subject: {request.subject}
Grade: {request.gradeLevel}

USER FEEDBACK:
"{request.feedback}"

CURRENT PLAN JSON:
{current_plan_json}

OUTPUT FORMAT: Valid JSON matching the original schema (sessions, chunkPlan,
differentiation, assessments, reflectionPrompts, backupPlan, etc.). Preserve
the multi-session structure and all quality rules above.
"""

        class_duration = 45
        if request.currentPlan.get("sessions"):
            class_duration = request.currentPlan["sessions"][0].get("duration", 45)

        result = await generate_and_validate(system_message, prompt, class_duration)

        concepts = [Concept(**c) for c in result.get("concepts", [])]
        sessions = parse_sessions(result.get("sessions", []), class_duration)

        assessments_data = result.get("assessments", {})
        assessments = AssessmentPlan(
            formative=assessments_data.get("formative", []),
            summative=assessments_data.get("summative", "End-of-lesson assessment"),
        )

        diff_data = result.get("differentiation", {})
        differentiation = DifferentiationPlan(
            support=diff_data.get("support", []),
            extension=diff_data.get("extension", []),
            accommodations=diff_data.get("accommodations"),
        )

        reflection_data = result.get("reflectionPrompts")
        reflection = ReflectionPrompts(**reflection_data) if reflection_data else None

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
            reflectionPrompts=reflection,
            totalSessions=len(sessions),
            totalDuration=sum(s.duration for s in sessions),
        )

    except HTTPException:
        raise
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
