from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any

# Import lesson schemas (new Chalkie-inspired schemas)
from app.models.lesson_schema import (
    BloomLevel,
    PedagogicalModel,
    SlideType,
    LessonMetadata,
    LearningObjective,
    VocabularyTerm,
    LearningStructure,
    LessonDeck,
    DifferentiationLevel,
    VisualMetadata,
    Slide,
    DeckGenerateRequest,
    DeckGenerateResponse,
    DeckGenerateResponseLegacy,
    PPTXRenderRequest,
)

class ActivityGenerateRequest(BaseModel):
    topic: str
    subject: str
    duration: int
    activityType: str
    gradeLevel: str

class ActivityGenerateResponse(BaseModel):
    title: str
    materials: List[str] = []
    steps: List[str] = []
    learningOutcomes: List[str] = []  # Made optional with default to handle AI inconsistency

class DetailedTopic(BaseModel):
    name: str
    periodsRequired: int = 1
    learningObjectives: List[str] = []
    keyConcepts: List[str] = []

class LessonPlanGenerateRequest(BaseModel):
    topics: List[DetailedTopic]
    subject: str
    gradeLevel: str
    classDuration: int = 45  # Duration per class period in minutes

    @field_validator('topics', mode='before')
    @classmethod
    def transform_topics(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [{"name": v, "periodsRequired": 1, "learningObjectives": [], "keyConcepts": []}]
        if isinstance(v, list):
            transformed = []
            for item in v:
                if isinstance(item, str):
                    transformed.append({"name": item, "periodsRequired": 1, "learningObjectives": [], "keyConcepts": []})
                elif isinstance(item, dict):
                    transformed.append({
                        "name": item.get("name") or item.get("title") or "Topic",
                        "periodsRequired": item.get("periodsRequired", 1),
                        "learningObjectives": item.get("learningObjectives", []),
                        "keyConcepts": item.get("keyConcepts") or item.get("keyPoints") or []
                    })
                else:
                    transformed.append(item)
            return transformed
        return v


class ChunkBlock(BaseModel):
    """One attention-span-sized chunk of the main teaching block.

    Long, unbroken explanation is the #1 cause of lessons losing a class.
    Instead of a single 'main_time' blob, the session's core instruction
    is planned as a sequence of short chunks, each ending in a deliberate
    check-in, matched to the grade band's realistic attention span.
    """
    order: int
    focus: str                     # what this chunk teaches (a slice of the objective)
    duration: int                   # minutes, sized to the grade's attention span
    checkIn: str                    # the quick question/signal used to end this chunk


class ReflectionPrompts(BaseModel):
    """The 5-minute post-lesson reflection habit, generated per lesson so the
    teacher doesn't have to remember to ask themselves these after class."""
    mostConfusingPoint: str        # anticipated point of confusion to watch for
    strongestExplanation: str      # which planned explanation/example is likely strongest
    likelyDiscussionSpark: str     # which question is likely to spark the most discussion
    objectiveCheckQuestion: str    # a question the teacher can ask themselves to verify the objective landed
    suggestedRevision: str         # a placeholder prompt: "what would you change next time?"


class LessonStep(BaseModel):
    order: int
    activity: str
    duration: int
    method: str  # "I Do", "We Do", "You Do", "Discussion", etc.
    resources: List[str]
    notes: Optional[str] = None
    checkInPrompt: Optional[str] = None
    difficultyNote: Optional[str] = None


class Concept(BaseModel):
    id: str
    name: str
    description: str


class SessionIntroduction(BaseModel):
    """Introduction/Hook section for each session"""
    hook: str  # Engaging opening activity to capture interest
    priorKnowledge: str  # How to activate prior knowledge
    agendaShare: str  # What to tell students about today's lesson


class CheckForUnderstanding(BaseModel):
    """Formative assessment during the lesson"""
    type: str  # "questioning", "quick_quiz", "whiteboard", "verbal_summary", etc.
    prompt: str
    expectedResponse: Optional[str] = None


class LessonSession(BaseModel):
    """Single class session within a multi-session lesson plan"""
    sessionNumber: int
    title: str
    duration: int  # In minutes
    objectives: List[str]  # SWBAT objectives for this session
    introduction: SessionIntroduction
    activities: List[LessonStep]
    checkForUnderstanding: List[CheckForUnderstanding]
    closure: str  # Summary and preview of next session
    chunkPlan: List[ChunkBlock] = Field(default_factory=list)
    backupPlan: Optional[str] = None


class AssessmentPlan(BaseModel):
    """Overall assessment strategy for the lesson"""
    formative: List[str]  # Ongoing checks during lessons
    summative: str  # End assessment or project


class DifferentiationPlan(BaseModel):
    """Strategies for diverse learners"""
    support: List[str]  # For struggling learners
    extension: List[str]  # For advanced learners
    accommodations: Optional[List[str]] = None  # For IEP/ELL students


class LessonPlanGenerateResponse(BaseModel):
    title: str
    objectives: List[str]  # Master objectives for entire unit
    prerequisites: List[str]  # What students should already know
    standards: Optional[List[str]] = None  # Curriculum standards alignment
    concepts: List[Concept]
    sessions: List[LessonSession]  # Multiple class sessions
    assessments: AssessmentPlan
    resources: List[str]
    differentiation: DifferentiationPlan
    totalSessions: int
    totalDuration: int  # Total minutes across all sessions
    reflectionPrompts: Optional[ReflectionPrompts] = None

class DoubtRequest(BaseModel):
    question: str
    subject: Optional[str] = None
    gradeLevel: Optional[str] = None  # Student's grade for age-appropriate answers


class DoubtResponse(BaseModel):
    question: str
    solution: str
    subject: str
    relatedConcepts: List[str]
    similarProblems: List[str]

class FollowUpRequest(BaseModel):
    originalQuestion: str
    followUpQuestion: str
    previousContext: Optional[str] = None

class FollowUpResponse(BaseModel):
    answer: str
    clarification: Optional[str] = None

# Curriculum Plan Schemas
class CurriculumPlanRequest(BaseModel):
    gradeLevel: str
    subject: str

class TopicPlan(BaseModel):
    name: str
    objectives: List[str]
    teachingMinutes: int
    periods: int
    keyPoints: List[str]

class ChapterPlan(BaseModel):
    name: str
    topics: List[TopicPlan]
    totalMinutes: int
    totalPeriods: int

class CurriculumPlanResponse(BaseModel):
    title: str
    subject: str
    gradeLevel: str
    totalHours: int
    totalPeriods: int
    chapters: List[ChapterPlan]


# Quiz Generator Schemas
class QuizQuestion(BaseModel):
    content: str
    type: str  # 'multiple-choice', 'true-false', 'short-answer'
    options: Optional[List[str]] = None
    answer: str
    explanation: Optional[str] = None
    difficulty: Optional[str] = "medium"

class QuizGenerateRequest(BaseModel):
    classLevel: str
    subject: str
    chapter: str
    topic: str
    count: Optional[int] = 5
    additionalInstructions: Optional[str] = None  # Custom instructions from teacher

class QuizGenerateResponse(BaseModel):
    questions: List[QuizQuestion]


