from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class VisualMetadata(BaseModel):
    """Metadata for slide visualizations"""
    visualType: Optional[str] = None  # 'diagram', 'chart', 'math', 'illustration', 'none'
    visualConfig: Optional[Dict[str, Any]] = None  # Tool-specific configuration
    confidence: Optional[float] = None  # Confidence score 0-100
    generatedBy: Optional[str] = None  # 'mermaid', 'chartjs', 'latex', 'dalle3'
    reasoning: Optional[str] = None  # Why this visual type was chosen

class Slide(BaseModel):
    title: str
    content: str
    order: int
    imageUrl: Optional[str] = None
    visualMetadata: Optional[VisualMetadata] = None  # NEW: Visual generation metadata

class DeckGenerateRequest(BaseModel):
    topics: List[str] = []  # List of topics from curriculum
    topic: Optional[str] = None  # Backward compatibility for single topic
    subject: str
    gradeLevel: str
    chapter: Optional[str] = None  # Chapter name from curriculum
    numSlides: int = 10
    structuredFormat: Optional[bool] = False  # Use structured format (Def -> Details -> Q1 -> Q2 -> Q3)

class DeckGenerateResponse(BaseModel):
    title: str
    slides: List[Slide]

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

