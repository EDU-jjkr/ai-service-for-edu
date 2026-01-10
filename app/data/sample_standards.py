"""
Sample Curriculum Standards for Testing
CBSE (Central Board of Secondary Education) - India
"""

import logging

# Sample standards for Science, Grade 8
CBSE_SCIENCE_GRADE8 = [
    {
        "standard_id": "CBSE-SCI-8-01",
        "text": "Explain the process of photosynthesis and identify the role of chlorophyll, light, carbon dioxide, and water in this process.",
        "curriculum": "CBSE",
        "subject": "Science",
        "grade": "8",
        "chapter": "Photosynthesis",
        "learning_outcomes": ["Define photosynthesis", "Identify raw materials", "Explain the role of chlorophyll"]
    },
    {
        "standard_id": "CBSE-SCI-8-02",
        "text": "Understand and describe the water cycle including evaporation, condensation, and precipitation.",
        "curriculum": "CBSE",
        "subject": "Science",
        "grade": "8",
        "chapter": "Water Cycle",
        "learning_outcomes": ["Describe evaporation", "Explain condensation", "Understand precipitation"]
    },
    {
        "standard_id": "CBSE-SCI-8-03",
        "text": "Classify living organisms into different kingdoms based on their characteristics.",
        "curriculum": "CBSE",
        "subject": "Science",
        "grade": "8",
        "chapter": "Classification",
        "learning_outcomes": ["Understand kingdoms", "Classify organisms", "Identify characteristics"]
    },
    {
        "standard_id": "CBSE-SCI-8-04",
        "text": "Explain the laws of motion and apply them to real-world scenarios.",
        "curriculum": "CBSE",
        "subject": "Science",
        "grade": "8",
        "chapter": "Force and Motion",
        "learning_outcomes": ["State Newton's laws", "Apply laws to scenarios", "Calculate force and acceleration"]
    },
    {
        "standard_id": "CBSE-SCI-8-05",
        "text": "Understand the concept of cells as the basic structural and functional unit of life.",
        "curriculum": "CBSE",
        "subject": "Science",
        "grade": "8",
        "chapter": "Cell Structure",
        "learning_outcomes": ["Identify cell parts", "Differentiate plant and animal cells", "Understand cell functions"]
    }
]

# Sample standards for Mathematics, Grade 8
CBSE_MATH_GRADE8 = [
    {
        "standard_id": "CBSE-MATH-8-01",
        "text": "Solve linear equations in one variable and verify the solutions.",
        "curriculum": "CBSE",
        "subject": "Mathematics",
        "grade": "8",
        "chapter": "Linear Equations",
        "learning_outcomes": ["Solve linear equations", "Verify solutions", "Apply to word problems"]
    },
    {
        "standard_id": "CBSE-MATH-8-02",
        "text": "Understand and apply the concepts of rational numbers including operations and properties.",
        "curriculum": "CBSE",
        "subject": "Mathematics",
        "grade": "8",
        "chapter": "Rational Numbers",
        "learning_outcomes": ["Perform operations on rational numbers", "Understand properties", "Represent on number line"]
    },
    {
        "standard_id": "CBSE-MATH-8-03",
        "text": "Calculate the area and perimeter of various geometric shapes including circles, triangles, and quadrilaterals.",
        "curriculum": "CBSE",
        "subject": "Mathematics",
        "grade": "8",
        "chapter": "Mensuration",
        "learning_outcomes": ["Calculate area of circles", "Find perimeter of polygons", "Solve mensuration problems"]
    }
]

# Sample standards for English, Grade 8
CBSE_ENGLISH_GRADE8 = [
    {
        "standard_id": "CBSE-ENG-8-01",
        "text": "Read and analyze literary texts to identify themes, character development, and plot structure.",
        "curriculum": "CBSE",
        "subject": "English",
        "grade": "8",
        "chapter": "Literature Analysis",
        "learning_outcomes": ["Identify themes", "Analyze characters", "Understand plot structure"]
    },
    {
        "standard_id": "CBSE-ENG-8-02",
        "text": "Write well-structured essays with clear introduction, body paragraphs, and conclusion.",
        "curriculum": "CBSE",
        "subject": "English",
        "grade": "8",
        "chapter": "Essay Writing",
        "learning_outcomes": ["Structure essays", "Write thesis statements", "Develop arguments"]
    }
]

# Combine all standards
ALL_SAMPLE_STANDARDS = (
    CBSE_SCIENCE_GRADE8 +
    CBSE_MATH_GRADE8 +
    CBSE_ENGLISH_GRADE8
)


async def seed_sample_standards():
    """
    Seed the database with sample CBSE standards.
    
    Call this function to populate Qdrant with test data.
    """
    from app.services.rag_service import get_curriculum_rag
    
    rag = get_curriculum_rag()
    
    print("🌱 Seeding sample curriculum standards...")
    
    await rag.ingest_standards_bulk(ALL_SAMPLE_STANDARDS)
    
    stats = await rag.get_collection_stats()
    print(f"✅ Seeding complete!")
    print(f"📊 Total standards in database: {stats.get('total_standards', 0)}")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    
    # Run seeding
    asyncio.run(seed_sample_standards())
