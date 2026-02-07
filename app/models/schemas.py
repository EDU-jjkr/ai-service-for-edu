from pydantic import BaseModel, field_validator
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
    DeckGenerateResponseLegacy
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

class LessonPlanGenerateRequest(BaseModel):
    topics: List[str]
    subject: str
    gradeLevel: str
    classDuration: int = 45  # Duration per class period in minutes
    # AI will determine number of sessions based on topic count and complexity


class LessonStep(BaseModel):
    order: int
    activity: str
    duration: int
    method: str  # "I Do", "We Do", "You Do", "Discussion", etc.
    resources: List[str]
    notes: Optional[str] = None


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


