from typing import Optional, List, Dict
from pydantic import BaseModel

# Mock schema since the full LessonPlan schema isn't fully defined as a root entity yet
class MockLessonPlan(BaseModel):
    id: str
    title: str
    subject: str
    grade_level: str
    objectives: List[str]

# In-memory storage for MVP. 
_mock_db: Dict[str, MockLessonPlan] = {}

class LessonPlanRepository:
    """Repository layer for persisting and retrieving Lesson Plans"""
    
    @staticmethod
    async def save_plan(plan: MockLessonPlan) -> str:
        """Saves a new lesson plan or updates an existing one"""
        if not plan.id:
            import uuid
            plan.id = str(uuid.uuid4())
            
        _mock_db[plan.id] = plan
        return plan.id
        
    @staticmethod
    async def get_plan(plan_id: str) -> Optional[MockLessonPlan]:
        """Retrieves a lesson plan by its ID"""
        return _mock_db.get(plan_id)
