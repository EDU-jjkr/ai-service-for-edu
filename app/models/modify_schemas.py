from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class DeckModifyRequest(BaseModel):
    currentDeck: Dict[str, Any]
    feedback: str
    subject: str
    gradeLevel: str

class LessonPlanModifyRequest(BaseModel):
    currentPlan: Dict[str, Any]
    feedback: str
    subject: str
    gradeLevel: str
