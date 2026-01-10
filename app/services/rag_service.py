"""
RAG Service for Curriculum Standards (OpenAI Embeddings Version)
Uses Qdrant vector database with OpenAI embeddings
"""

import os
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from openai import OpenAI
import logging
import hashlib

logger = logging.getLogger(__name__)


class CurriculumRAG:
    """
    Retrieval-Augmented Generation service for curriculum standards.
    
    Uses OpenAI embeddings (text-embedding-3-small) instead of sentence-transformers
    to avoid dependency conflicts.
    """
    
    def __init__(self):
        # Initialize Qdrant client
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.collection_name = "curriculum_standards"
        
        # Initialize OpenAI client for embeddings
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dim = 1536  # text-embedding-3-small dimensions
        
        # Ensure collection exists
        self._ensure_collection()
        
        logger.info(f"CurriculumRAG initialized. Connected to Qdrant at {qdrant_host}:{qdrant_port}")
        logger.info(f"Using OpenAI embeddings: {self.embedding_model}")
    
    def _ensure_collection(self):
        """Create the curriculum_standards collection if it doesn't exist."""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                
                logger.info(f"✓ Collection created: {self.collection_name}")
            else:
                logger.info(f"✓ Collection already exists: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            raise
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding using OpenAI API.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats (embedding vector)
        """
        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    async def ingest_standard(
        self,
        standard_id: str,
        standard_text: str,
        curriculum: str,
        subject: str,
        grade: str,
        metadata: Dict[str, Any] = None
    ):
        """
        Ingest a single curriculum standard into the vector database.
        
        Args:
            standard_id: Unique identifier (e.g., "RL.5.1", "CBSE-SCI-8-01")
            standard_text: Full text of the standard
            curriculum: Curriculum system (e.g., "CBSE", "ICSE", "Common Core")
            subject: Subject area (e.g., "Science", "Mathematics")
            grade: Grade level (e.g., "5", "8")
            metadata: Additional metadata dict
        """
        try:
            # Generate embedding
            embedding = self._get_embedding(standard_text)
            
            # Create unique point ID
            point_id = int(hashlib.md5(standard_id.encode()).hexdigest()[:8], 16)
            
            # Prepare payload
            payload = {
                "standard_id": standard_id,
                "text": standard_text,
                "curriculum": curriculum,
                "subject": subject,
                "grade": grade,
                **(metadata or {})
            }
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload
                    )
                ]
            )
            
            logger.info(f"✓ Ingested standard: {standard_id}")
            
        except Exception as e:
            logger.error(f"Failed to ingest standard {standard_id}: {e}")
    
    async def ingest_standards_bulk(self, standards: List[Dict[str, Any]]):
        """
        Ingest multiple standards at once.
        
        Args:
            standards: List of dicts with keys: standard_id, text, curriculum, subject, grade
        """
        points = []
        
        for std in standards:
            try:
                # Generate embedding
                embedding = self._get_embedding(std['text'])
                
                # Create point ID
                point_id = int(hashlib.md5(std['standard_id'].encode()).hexdigest()[:8], 16)
                
                # Create point
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=std
                    )
                )
                
            except Exception as e:
                logger.error(f"Failed to prepare standard {std.get('standard_id')}: {e}")
        
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"✓ Bulk ingested {len(points)} standards")
    
    async def retrieve_relevant_standards(
        self,
        topic: str,
        subject: str,
        grade: str,
        curriculum: str = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant standards using hybrid search.
        
        Args:
            topic: Topic or query string (e.g., "photosynthesis")
            subject: Subject filter (e.g., "Science")
            grade: Grade filter (e.g., "8")
            curriculum: Optional curriculum filter (e.g., "CBSE")
            top_k: Number of standards to retrieve
            
        Returns:
            List of standard dicts with: standard_id, text, score
        """
        try:
            # Generate query embedding
            query_vector = self._get_embedding(topic)
            
            # Build filters
            must_conditions = [
                FieldCondition(key="subject", match=MatchValue(value=subject)),
                FieldCondition(key="grade", match=MatchValue(value=grade))
            ]
            
            if curriculum:
                must_conditions.append(
                    FieldCondition(key="curriculum", match=MatchValue(value=curriculum))
                )
            
            # Search with filters
            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=Filter(must=must_conditions) if must_conditions else None,
                limit=top_k
            ).points
            
            # Format results
            standards = []
            for hit in search_result:
                standards.append({
                    "standard_id": hit.payload.get("standard_id"),
                    "text": hit.payload.get("text"),
                    "score": hit.score,
                    "curriculum": hit.payload.get("curriculum"),
                    "subject": hit.payload.get("subject"),
                    "grade": hit.payload.get("grade")
                })
            
            logger.info(f"Retrieved {len(standards)} standards for topic: {topic}")
            
            return standards
            
        except Exception as e:
            logger.error(f"Failed to retrieve standards: {e}")
            return []
    
    def inject_into_prompt(self, standards: List[Dict[str, Any]], base_prompt: str) -> str:
        """
        Inject retrieved standards into a system prompt.
        
        Args:
            standards: List of standard dicts
            base_prompt: Original system prompt
            
        Returns:
            Enhanced prompt with standards context
        """
        if not standards:
            return base_prompt
        
        standards_text = "\n\n🎯 CURRICULUM STANDARDS TO ALIGN WITH:\n"
        
        for std in standards:
            standards_text += f"\n- [{std['standard_id']}] {std['text']}"
        
        standards_text += "\n\n⚠️ IMPORTANT: Your lesson content MUST align with these standards.\n"
        
        # Inject before the main task
        enhanced_prompt = base_prompt + standards_text
        
        return enhanced_prompt
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the curriculum standards collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            
            return {
                "total_standards": info.points_count,
                "vector_size": info.config.params.vectors.size,
                "distance_metric": info.config.params.vectors.distance
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}


# Singleton instance
_curriculum_rag = None

def get_curriculum_rag() -> CurriculumRAG:
    """Get the global CurriculumRAG instance (singleton pattern)."""
    global _curriculum_rag
    if _curriculum_rag is None:
        _curriculum_rag = CurriculumRAG()
    return _curriculum_rag
