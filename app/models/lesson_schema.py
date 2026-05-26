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
    pedagogical_flow: str = "default_classroom"
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


class PedagogicalRole(str, Enum):
    """Pedagogical roles for structured slides"""
    HOOK = "hook"
    EXPLAIN_CORE = "explain_core"
    EXPLAIN_DEEPEN = "explain_deepen"
    WORKED_EXAMPLE = "worked_example"
    COMPARE_EXAMPLE = "compare_example"
    GUIDED_PRACTICE = "guided_practice"
    INDEPENDENT_PRACTICE = "independent_practice"
    SUMMARY = "summary"


class ContentMode(str, Enum):
    """Primary content mode for structured slides"""
    TEXT_ONLY = "text_only"
    IMAGE_SUPPORT = "image_support"
    DIAGRAM = "diagram"
    CHART = "chart"
    EQUATION = "equation"
    COMPARISON = "comparison"
    QUESTION = "question"


class DensityLevel(str, Enum):
    """Allowed density levels for structured slides"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImportanceLevel(str, Enum):
    """Allowed importance levels for structured slides"""
    PRIMARY = "primary"
    SECONDARY = "secondary"


class VisualPriority(str, Enum):
    """Allowed priorities for visual intent"""
    REQUIRED = "required"
    OPTIONAL = "optional"


class VisualSourceStrategy(str, Enum):
    """Allowed visual sourcing strategies"""
    STOCK = "stock"
    GENERATED = "generated"
    DIAGRAMMATIC = "diagrammatic"
    RENDERER_NATIVE = "renderer_native"


class ContentBlock(BaseModel):
    """Typed content block for schema-aware slide rendering"""
    type: str
    text: Optional[str] = None
    items: List[str] = Field(default_factory=list)
    value: Optional[str] = None


class VisualIntent(BaseModel):
    """Rendering intent for non-text content"""
    purpose: str
    assetType: str
    priority: VisualPriority = VisualPriority.OPTIONAL
    sourceStrategy: VisualSourceStrategy = VisualSourceStrategy.RENDERER_NATIVE


class EditingHints(BaseModel):
    """Editor constraints for structured slide updates"""
    locked: bool = False
    canAddBlocks: List[str] = Field(default_factory=list)
    canRemoveBlocks: List[str] = Field(default_factory=list)
    notes: Dict[str, Any] = Field(default_factory=dict)


class PracticeMetadata(BaseModel):
    """Practice-slide specific metadata"""
    difficulty: Optional[str] = None
    answerMode: Optional[str] = None
    stepCount: Optional[int] = None
    misconception: Optional[str] = None


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
    clusterId: Optional[str] = None
    pedagogicalRole: Optional[PedagogicalRole] = None
    instructionalGoal: Optional[str] = None
    contentMode: Optional[ContentMode] = None
    contentBlocks: List[ContentBlock] = Field(default_factory=list)
    layoutCandidates: List[str] = Field(default_factory=list)
    density: Optional[DensityLevel] = None
    importance: Optional[ImportanceLevel] = None
    visualIntent: Optional[VisualIntent] = None
    editingHints: Optional[EditingHints] = None
    practiceMetadata: Optional[PracticeMetadata] = None

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
    aiProvider: Optional[str] = None
    aiModel: Optional[str] = None
    chapter: Optional[str] = None  # Chapter name from curriculum
    numSlides: int = 10
    structuredFormat: Optional[bool] = False  # Use structured format (Def -> Details -> Q1 -> Q2 -> Q3)
    theme: str = "default"  # PowerPoint theme
    standards: List[str] = []  # Specific curriculum standards to align with
    pedagogical_model: Optional[PedagogicalModel] = PedagogicalModel.I_DO_WE_DO_YOU_DO
    pedagogyFlow: Optional[str] = "default_classroom"
    level: Optional[DifferentiationLevel] = DifferentiationLevel.CORE
    additionalInstructions: Optional[str] = None  # Custom instructions from teacher


class DeckGenerateResponse(BaseModel):
    """Response from deck generation"""
    lesson: LessonDeck  # Complete lesson deck
    title: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    structure: Optional[Dict[str, Any]] = None
    slides: List[Slide] = []


# Keep legacy response for backward compatibility
class DeckGenerateResponseLegacy(BaseModel):
    """Legacy response format"""
    title: str
    slides: List[Slide]


class PPTXRenderRequest(BaseModel):
    """Render a canonical lesson deck to PPTX."""
    lesson: LessonDeck
    theme: Optional[str] = None


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
    classDuration: int = 45  # Duration per class period in minutes


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
