from typing import Optional, List, Dict
from app.models.lesson_schema import LessonDeck

# In-memory storage for MVP. 
# TODO: Replace with actual Database connection (PostgreSQL/MongoDB)
_mock_db: Dict[str, LessonDeck] = {}
_mock_versions: Dict[str, List[LessonDeck]] = {}

class DeckRepository:
    """Repository layer for persisting and retrieving Lesson Decks"""
    
    @staticmethod
    async def save_deck(deck: LessonDeck) -> str:
        """Saves a new deck or updates an existing one"""
        if not deck.id:
            import uuid
            deck.id = str(uuid.uuid4())
            
        _mock_db[deck.id] = deck
        
        # Save version history
        if deck.id not in _mock_versions:
            _mock_versions[deck.id] = []
        # Create deep copy for history
        _mock_versions[deck.id].append(deck.model_copy(deep=True))
        
        return deck.id
        
    @staticmethod
    async def get_deck(deck_id: str) -> Optional[LessonDeck]:
        """Retrieves a deck by its ID"""
        return _mock_db.get(deck_id)
        
    @staticmethod
    async def get_versions(deck_id: str) -> List[LessonDeck]:
        """Retrieves all historical versions of a deck"""
        return _mock_versions.get(deck_id, [])
