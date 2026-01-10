from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class BloomLevel(str, Enum):
    """Bloom's Taxonomy Cognitive Levels"""
    REMEMBER = "REMEMBER"      # Recall facts, terms, basic concepts
    UNDERSTAND = "UNDERSTAND"  # Explain ideas, summarize
    APPLY = "APPLY"           # Use in new situations, solve problems
    ANALYZE = "ANALYZE"       # Draw connections, differentiate
    EVALUATE = "EVALUATE"     # Justify, critique, judge
    CREATE = "CREATE"         # Design, construct, produce


class PedagogicalModel(str, Enum):
    """Teaching models"""
    I_DO_WE_DO_YOU_DO = "I_DO_WE_DO_YOU_DO"
    DIRECT_INSTRUCTION = "DIRECT_INSTRUCTION"
    INQUIRY_BASED = "INQUIRY_BASED"
    COLLABORATIVE = "COLLABORATIVE"


class SlideType(str, Enum):
    """Types of slides in a lesson"""
    INTRODUCTION = "INTRODUCTION"
    CONCEPT = "CONCEPT"
    ACTIVITY = "ACTIVITY"
    ASSESSMENT = "ASSESSMENT"
    SUMMARY = "SUMMARY"


class LessonMetadata(BaseModel):
    """Metadata for the lesson deck"""
    lesson_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    subject: str
    grade: str
    standards: List[str] = []  # Aligned curriculum standards (e.g., ["RL.5.1", "RL.5.2"])
    theme: str = "default"  # PowerPoint theme name
    pedagogical_model: PedagogicalModel = PedagogicalModel.I_DO_WE_DO_YOU_DO
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LearningObjective(BaseModel):
    """Learning objective with Bloom's level"""
    objective: str
    bloom_level: BloomLevel


class VocabularyTerm(BaseModel):
    """Vocabulary term with definition"""
    term: str
    definition: str
    grade_appropriate: bool = True


class LearningStructure(BaseModel):
    """Learning structure for the lesson"""
    learning_objectives: List[LearningObjective]
    vocabulary: List[VocabularyTerm]
    prerequisites: List[str] = []
    bloom_progression: List[BloomLevel] = []  # Expected cognitive progression through lesson


class VisualMetadata(BaseModel):
    """Metadata for slide visualizations"""
    visualType: Optional[str] = None  # 'diagram', 'chart', 'math', 'illustration', 'stock_photo'
    visualConfig: Optional[Dict[str, Any]] = None  # Tool-specific configuration
    confidence: Optional[float] = None  # Confidence score 0-100
    generatedBy: Optional[str] = None  # 'mermaid', 'chartjs', 'latex', 'dalle3', 'unsplash', 'pexels'
    reasoning: Optional[str] = None  # Why this visual type was chosen


class Slide(BaseModel):
    """Individual slide in the lesson deck"""
    title: str
    content: str
    order: int
    slideType: SlideType = SlideType.CONCEPT
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND  # Cognitive level of this slide
    objective: Optional[str] = None  # Specific learning objective for this slide
    speakerNotes: Optional[str] = None  # Notes for the teacher
    imageQuery: Optional[str] = None  # Search query for stock photos (e.g., "sun shining on ocean")
    imageUrl: Optional[str] = None  # Deprecated: kept for backward compatibility
    visualMetadata: Optional[VisualMetadata] = None

    @field_validator('content', mode='before')
    @classmethod
    def serialize_content(cls, v: Any) -> str:
        """Ensure content is always a string"""
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return "\n".join([str(item) for item in v])
        if isinstance(v, dict):
            import json
            return json.dumps(v)
        return str(v)


class LessonDeck(BaseModel):
    """Complete lesson structure - The Rosetta Stone"""
    meta: LessonMetadata
    structure: LearningStructure
    slides: List[Slide]


class DifferentiationLevel(str, Enum):
    """Levels of differentiation"""
    SUPPORT = "SUPPORT"      # Simplified for struggling learners (Bloom's 1-2)
    CORE = "CORE"           # Standard level (Bloom's 1-3)
    EXTENSION = "EXTENSION"  # Advanced for gifted learners (Bloom's 4-6)


# ===== REQUEST/RESPONSE SCHEMAS =====

class DeckGenerateRequest(BaseModel):
    """Request to generate a deck"""
    topics: List[str] = []  # List of topics from curriculum
    topic: Optional[str] = None  # Backward compatibility for single topic
    subject: str
    gradeLevel: str
    chapter: Optional[str] = None  # Chapter name from curriculum
    numSlides: int = 10
    structuredFormat: Optional[bool] = False  # Use structured format (Def -> Details -> Q1 -> Q2 -> Q3)
    theme: str = "default"  # PowerPoint theme
    standards: List[str] = []  # Specific curriculum standards to align with
    pedagogical_model: Optional[PedagogicalModel] = PedagogicalModel.I_DO_WE_DO_YOU_DO
    level: Optional[DifferentiationLevel] = DifferentiationLevel.CORE


class DeckGenerateResponse(BaseModel):
    """Response from deck generation"""
    lesson: LessonDeck  # Complete lesson deck


# Keep legacy response for backward compatibility
class DeckGenerateResponseLegacy(BaseModel):
    """Legacy response format"""
    title: str
    slides: List[Slide]


# ===== OTHER EXISTING SCHEMAS (Activity, LessonPlan, etc.) =====

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
    learningOutcomes: List[str] = []


class LessonPlanGenerateRequest(BaseModel):
    topics: List[str]
    subject: str
    gradeLevel: str
    totalDuration: int


class LessonStep(BaseModel):
    order: int
    activity: str
    duration: int
    method: str
    resources: List[str]


class Concept(BaseModel):
    id: str
    name: str
    description: str


class LessonPlanGenerateResponse(BaseModel):
    title: str
    objectives: List[str]
    concepts: List[Concept]
    sequence: List[LessonStep]
    assessments: List[str]
    resources: List[str]


class DoubtRequest(BaseModel):
    question: str
    subject: Optional[str] = None
    gradeLevel: Optional[str] = None


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
