"""
Comprehensive ISC/ICSE Curriculum Standards Seeding Script
Extracts standards from TypeScript curriculum and seeds into Qdrant
"""

import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from openai import OpenAI
import hashlib
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Comprehensive ISC/ICSE Standards extracted from curriculum.ts
ICSE_ISC_STANDARDS = [
    # Class 8 - ICSE - Mathematics
    {"standard_id": "ICSE-MATH-8-01", "text": "Understand properties of rational numbers and represent them on a number line", "curriculum": "ICSE", "subject": "Mathematics", "grade": "8", "chapter": "Rational Numbers"},
    {"standard_id": "ICSE-MATH-8-02", "text": "Apply laws of exponents and express numbers in standard form", "curriculum": "ICSE", "subject": "Mathematics", "grade": "8", "chapter": "Exponents and Powers"},
    {"standard_id": "ICSE-MATH-8-03", "text": "Solve linear equations in one variable and apply to word problems", "curriculum": "ICSE", "subject": "Mathematics", "grade": "8", "chapter": "Linear Equations"},
    {"standard_id": "ICSE-MATH-8-04", "text": "Calculate percentage, profit and loss, discount, and simple interest in various applications", "curriculum": "ICSE", "subject": "Mathematics", "grade": "8", "chapter": "Percentage and Its Applications"},
    {"standard_id": "ICSE-MATH-8-05", "text": "Compute compound interest using formula and apply to real-world scenarios", "curriculum": "ICSE", "subject": "Mathematics", "grade": "8", "chapter": "Compound Interest"},
    
    # Class 8 - ICSE - Science
    {"standard_id": "ICSE-PHY-8-01", "text": "Identify states of matter and explain changes of state with examples", "curriculum": "ICSE", "subject": "Physics", "grade": "8", "chapter": "Matter"},
    {"standard_id": "ICSE-PHY-8-02", "text": "Understand different types of forces and calculate pressure in fluids", "curriculum": "ICSE", "subject": "Physics", "grade": "8", "chapter": "Force and Pressure"},
    {"standard_id": "ICSE-PHY-8-03", "text": "Describe forms of energy and energy transformation processes", "curriculum": "ICSE", "subject": "Physics", "grade": "8", "chapter": "Energy"},
    {"standard_id": "ICSE-CHEM-8-01", "text": "Classify matter and describe its properties", "curriculum": "ICSE", "subject": "Chemistry", "grade": "8", "chapter": "Matter"},
    {"standard_id": "ICSE-CHEM-8-02", "text": "Differentiate between physical and chemical changes with examples", "curriculum": "ICSE", "subject": "Chemistry", "grade": "8", "chapter": "Physical and Chemical Changes"},
    {"standard_id": "ICSE-BIO-8-01", "text": "Explain transport of food and minerals in plants through xylem and phloem, and understand transpiration", "curriculum": "ICSE", "subject": "Biology", "grade": "8", "chapter": "Transport of Food and Minerals"},
    {"standard_id": "ICSE-BIO-8-02", "text": "Describe asexual and sexual reproduction in plants", "curriculum": "ICSE", "subject": "Biology", "grade": "8", "chapter": "Reproduction in Plants"},
    {"standard_id": "ICSE-BIO-8-03", "text": "Identify cell structure and functions of cell organelles", "curriculum": "ICSE", "subject": "Biology", "grade": "8", "chapter": "The Cell"},
    
    # Class 9 - ICSE - Mathematics
    {"standard_id": "ICSE-MATH-9-01", "text": "Understand properties of rational and irrational numbers including surds", "curriculum": "ICSE", "subject": "Mathematics", "grade": "9", "chapter": "Rational and Irrational Numbers"},
    {"standard_id": "ICSE-MATH-9-02", "text": "Solve simultaneous linear equations using graphical and algebraic methods", "curriculum": "ICSE", "subject": "Mathematics", "grade": "9", "chapter": "Simultaneous Linear Equations"},
    {"standard_id": "ICSE-MATH-9-03", "text": "Apply Pythagoras theorem to solve geometric problems", "curriculum": "ICSE", "subject": "Mathematics", "grade": "9", "chapter": "Pythagoras Theorem"},
    {"standard_id": "ICSE-MATH-9-04", "text": "Understand and apply trigonometric ratios (sine, cosine, tangent) and identities", "curriculum": "ICSE", "subject": "Mathematics", "grade": "9", "chapter": "Trigonometrical Ratios"},
    
    # Class 9 - ICSE - Science
    {"standard_id": "ICSE-PHY-9-01", "text": "Apply Newton's laws of motion and understand momentum and conservation of momentum", "curriculum": "ICSE", "subject": "Physics", "grade": "9", "chapter": "Laws of Motion"},
    {"standard_id": "ICSE-PHY-9-02", "text": "Understand pressure in fluids, buoyancy, and Archimedes' principle", "curriculum": "ICSE", "subject": "Physics", "grade": "9", "chapter": "Fluids"},
    {"standard_id": "ICSE-PHY-9-03", "text": "Explain reflection, refraction of light, and properties of lenses", "curriculum": "ICSE", "subject": "Physics", "grade": "9", "chapter": "Light"},
    {"standard_id": "ICSE-CHEM-9-01", "text": "Understand atomic structure including electron configuration and chemical bonding (ionic and covalent)", "curriculum": "ICSE", "subject": "Chemistry", "grade": "9", "chapter": "Atomic Structure and Chemical Bonding"},
    {"standard_id": "ICSE-CHEM-9-02", "text": "Understand the periodic table organization: periods, groups, and periodic trends", "curriculum": "ICSE", "subject": "Chemistry", "grade": "9", "chapter": "The Periodic Table"},
    {"standard_id": "ICSE-BIO-9-01", "text": "Explain the process of photosynthesis, respiration, and transpiration in plants", "curriculum": "ICSE", "subject": "Biology", "grade": "9", "chapter": "Plant Physiology"},
    {"standard_id": "ICSE-BIO-9-02", "text": "Understand human anatomy: digestive, circulatory, and respiratory systems", "curriculum": "ICSE", "subject": "Biology", "grade": "9", "chapter": "Human Anatomy and Physiology"},
    
    # Class 10 - ICSE - Mathematics
    {"standard_id": "ICSE-MATH-10-01", "text": "Solve quadratic equations using factorisation and quadratic formula, and determine nature of roots", "curriculum": "ICSE", "subject": "Mathematics", "grade": "10", "chapter": "Quadratic Equations"},
    {"standard_id": "ICSE-MATH-10-02", "text": "Understand arithmetic and geometric progressions: nth term and sum of n terms", "curriculum": "ICSE", "subject": "Mathematics", "grade": "10", "chapter": "Arithmetic and Geometric Progression"},
    {"standard_id": "ICSE-MATH-10-03", "text": "Apply similarity theorems to triangles and calculate areas of similar triangles", "curriculum": "ICSE", "subject": "Mathematics", "grade": "10", "chapter": "Similarity"},
    {"standard_id": "ICSE-MATH-10-04", "text": "Apply trigonometric identities and solve heights and distances problems", "curriculum": "ICSE", "subject": "Mathematics", "grade": "10", "chapter": "Trigonometry"},
    {"standard_id": "ICSE-MATH-10-05", "text": "Calculate surface area and volume of cylinders, cones, spheres, and combined solids", "curriculum": "ICSE", "subject": "Mathematics", "grade": "10", "chapter": "Mensuration"},
    
    # Class 10 - ICSE - Science
    {"standard_id": "ICSE-PHY-10-01", "text": "Understand work, energy, power, and simple machines with turning effect of force", "curriculum": "ICSE", "subject": "Physics", "grade": "10", "chapter": "Force, Work, Power and Energy"},
    {"standard_id": "ICSE-PHY-10-02", "text": "Explain refraction through lenses, spectrum formation, and correction of eye defects", "curriculum": "ICSE", "subject": "Physics", "grade": "10", "chapter": "Light"},
    {"standard_id": "ICSE-PHY-10-03", "text": "Apply Ohm's law, understand electrical circuits, household electricity, and magnetic effects of current", "curriculum": "ICSE", "subject": "Physics", "grade": "10", "chapter": "Electricity and Magnetism"},
    {"standard_id": "ICSE-CHEM-10-01", "text": "Understand periodic properties and periodicity in the periodic table", "curriculum": "ICSE", "subject": "Chemistry", "grade": "10", "chapter": "Periodic Table"},
    {"standard_id": "ICSE-CHEM-10-02", "text": "Understand mole concept, molar mass, and stoichiometric calculations", "curriculum": "ICSE", "subject": "Chemistry", "grade": "10", "chapter": "Mole Concept"},
    {"standard_id": "ICSE-CHEM-10-03", "text": "Explain electrolysis, electrolytes, electrode reactions, and applications", "curriculum": "ICSE", "subject": "Chemistry", "grade": "10", "chapter": "Electrolysis"},
    {"standard_id": "ICSE-BIO-10-01", "text": "Understand cell cycle, mitosis, and meiosis processes", "curriculum": "ICSE", "subject": "Biology", "grade": "10", "chapter": "Cell Cycle and Division"},
    {"standard_id": "ICSE-BIO-10-02", "text": "Apply Mendel's laws of inheritance and understand monohybrid and dihybrid crosses", "curriculum": "ICSE", "subject": "Biology", "grade": "10", "chapter": "Genetics"},
    
    # Class 11 - ISC - Mathematics
    {"standard_id": "ISC-MATH-11-01", "text": "Understand sets, types of sets, set operations, and Venn diagrams", "curriculum": "ISC", "subject": "Mathematics", "grade": "11", "chapter": "Sets"},
    {"standard_id": "ISC-MATH-11-02", "text": "Classify relations and functions, and understand composition of functions", "curriculum": "ISC", "subject": "Mathematics", "grade": "11", "chapter": "Relations and Functions"},
    {"standard_id": "ISC-MATH-11-03", "text": "Understand algebra of complex numbers, Argand plane, and polar form representation", "curriculum": "ISC", "subject": "Mathematics", "grade": "11", "chapter": "Complex Numbers"},
    {"standard_id": "ISC-MATH-11-04", "text": "Apply permutations and combinations using fundamental counting principle", "curriculum": "ISC", "subject": "Mathematics", "grade": "11", "chapter": "Permutations and Combinations"},
    {"standard_id": "ISC-MATH-11-05", "text": "Understand conic sections: circle, parabola, ellipse, and hyperbola", "curriculum": "ISC", "subject": "Mathematics", "grade": "11", "chapter": "Conic Sections"},
    {"standard_id": "ISC-MATH-11-06", "text": "Understand concept of limits and derivatives, and perform differentiation", "curriculum": "ISC", "subject": "Mathematics", "grade": "11", "chapter": "Limits and Derivatives"},
    
    # Class 11 - ISC - Science
    {"standard_id": "ISC-PHY-11-01", "text": "Understand kinematics: motion in straight line, plane, and projectile motion", "curriculum": "ISC", "subject": "Physics", "grade": "11", "chapter": "Kinematics"},
    {"standard_id": "ISC-PHY-11-02", "text": "Apply Newton's laws, understand friction and circular motion", "curriculum": "ISC", "subject": "Physics", "grade": "11", "chapter": "Laws of Motion"},
    {"standard_id": "ISC-PHY-11-03", "text": "Apply work-energy theorem, conservation of energy, and analyze collisions", "curriculum": "ISC", "subject": "Physics", "grade": "11", "chapter": "Work, Energy and Power"},
    {"standard_id": "ISC-PHY-11-04", "text": "Understand laws of thermodynamics, heat engines, and entropy", "curriculum": "ISC", "subject": "Physics", "grade": "11", "chapter": "Thermodynamics"},
    {"standard_id": "ISC-CHEM-11-01", "text": "Understand mole concept, atomic and molecular mass, and stoichiometry calculations", "curriculum": "ISC", "subject": "Chemistry", "grade": "11", "chapter": "Basic Concepts of Chemistry"},
    {"standard_id": "ISC-CHEM-11-02", "text": "Understand VSEPR theory, hybridisation, and molecular orbital theory", "curriculum": "ISC", "subject": "Chemistry", "grade": "11", "chapter": "Chemical Bonding"},
    {"standard_id": "ISC-CHEM-11-03", "text": "Understand chemical equilibrium, ionic equilibrium, pH, and buffers", "curriculum": "ISC", "subject": "Chemistry", "grade": "11", "chapter": "Equilibrium"},
    {"standard_id": "ISC-CHEM-11-04", "text": "Understand IUPAC nomenclature, isomerism, and reaction mechanisms in organic chemistry", "curriculum": "ISC", "subject": "Chemistry", "grade": "11", "chapter": "Organic Chemistry Basics"},
    {"standard_id": "ISC-BIO-11-01", "text": "Understand characteristics of life, taxonomy, and binomial nomenclature", "curriculum": "ISC", "subject": "Biology", "grade": "11", "chapter": "The Living World"},
    {"standard_id": "ISC-BIO-11-02", "text": "Understand plant classification: algae, bryophytes, pteridophytes, gymnosperms, angiosperms", "curriculum": "ISC", "subject": "Biology", "grade": "11", "chapter": "Plant Kingdom"},
    {"standard_id": "ISC-BIO-11-03", "text": "Explain photosynthesis: light reactions and Calvin cycle", "curriculum": "ISC", "subject": "Biology", "grade": "11", "chapter": "Photosynthesis"},
    {"standard_id": "ISC-BIO-11-04", "text": "Understand respiratory system and mechanism of gas exchange", "curriculum": "ISC", "subject": "Biology", "grade": "11", "chapter": "Breathing and Exchange of Gases"},
    
    # Class 12 - ISC - Mathematics
    {"standard_id": "ISC-MATH-12-01", "text": "Understand continuity and differentiability of functions", "curriculum": "ISC", "subject": "Mathematics", "grade": "12", "chapter": "Continuity and Differentiability"},
    {"standard_id": "ISC-MATH-12-02", "text": "Apply differentiation techniques and solve optimization problems", "curriculum": "ISC", "subject": "Mathematics", "grade": "12", "chapter": "Applications of Derivatives"},
    {"standard_id": "ISC-MATH-12-03", "text": "Understand indefinite and definite integrals and calculate areas under curves", "curriculum": "ISC", "subject": "Mathematics", "grade": "12", "chapter": "Integrals"},
    {"standard_id": "ISC-MATH-12-04", "text": "Solve differential equations and apply to real-world problems", "curriculum": "ISC", "subject": "Mathematics", "grade": "12", "chapter": "Differential Equations"},
    {"standard_id": "ISC-MATH-12-05", "text": "Understand vectors: operations, dot product, cross product, and applications", "curriculum": "ISC", "subject": "Mathematics", "grade": "12", "chapter": "Vectors"},
    {"standard_id": "ISC-MATH-12-06", "text": "Understand equations of lines and planes in 3D geometry", "curriculum": "ISC", "subject": "Mathematics", "grade": "12", "chapter": "Three Dimensional Geometry"},
    
    # Class 12 - ISC - Science
    {"standard_id": "ISC-PHY-12-01", "text": "Understand electric charges, fields, and Gauss's law", "curriculum": "ISC", "subject": "Physics", "grade": "12", "chapter": "Electrostatics"},
    {"standard_id": "ISC-PHY-12-02", "text": "Analyze electric circuits using Kirchhoff's laws", "curriculum": "ISC", "subject": "Physics", "grade": "12", "chapter": "Current Electricity"},
    {"standard_id": "ISC-PHY-12-03", "text": "Understand electromagnetic induction and Faraday's laws", "curriculum": "ISC", "subject": "Physics", "grade": "12", "chapter": "Electromagnetic Induction"},
    {"standard_id": "ISC-PHY-12-04", "text": "Understand wave optics: interference, diffraction, and polarization", "curriculum": "ISC", "subject": "Physics", "grade": "12", "chapter": "Wave Optics"},
    {"standard_id": "ISC-CHEM-12-01", "text": "Understand chemical kinetics: rate of reaction, order, and molecularity", "curriculum": "ISC", "subject": "Chemistry", "grade": "12", "chapter": "Chemical Kinetics"},
    {"standard_id": "ISC-CHEM-12-02", "text": "Understand electrochemistry: electrode potential, Nernst equation, and electrochemical cells", "curriculum": "ISC", "subject": "Chemistry", "grade": "12", "chapter": "Electrochemistry"},
    {"standard_id": "ISC-CHEM-12-03", "text": "Understand coordination compounds: nomenclature, bonding theories, and isomerism", "curriculum": "ISC", "subject": "Chemistry", "grade": "12", "chapter": "Coordination Compounds"},
    {"standard_id": "ISC-BIO-12-01", "text": "Understand DNA structure, replication, and transcription processes", "curriculum": "ISC", "subject": "Biology", "grade": "12", "chapter": "Molecular Basis of Inheritance"},
    {"standard_id": "ISC-BIO-12-02", "text": "Understand principles of biotechnology and genetic engineering", "curriculum": "ISC", "subject": "Biology", "grade": "12", "chapter": "Biotechnology"},
    {"standard_id": "ISC-BIO-12-03", "text": "Understand ecosystems: structure, energy flow, and ecosystem services", "curriculum": "ISC", "subject": "Biology", "grade": "12", "chapter": "Ecosystem"},
]

async def seed_curriculum_standards():
    """Seed Qdrant with comprehensive ISC/ICSE standards"""
    print("🌱 Seeding ISC/ICSE Curriculum Standards (Classes 8-12)...")
    print(f"📚 Total standards to seed: {len(ICSE_ISC_STANDARDS)}\n")
    
    # Connect to Qdrant
    client = QdrantClient(host="localhost", port=6333)
    
    # Initialize OpenAI
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    collection_name = "curriculum_standards"
    
    # Create collection if needed
    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if collection_name not in collection_names:
            print(f"Creating collection: {collection_name}")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
            print("✓ Collection created\n")
        else:
            print(f"✓ Collection already exists\n")
    except Exception as e:
        print(f"❌ Error with collection: {e}")
        return
    
    # Insert standards in batches
    print("📥 Generating embeddings and inserting standards...")
    print("(This will take a few minutes due to OpenAI API rate limits)\n")
    
    batch_size = 10
    points = []
    
    for i, std in enumerate(ICSE_ISC_STANDARDS, 1):
        try:
            # Generate embedding using OpenAI
            response = openai_client.embeddings.create(
                input=std['text'],
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            
            # Create point ID
            point_id = int(hashlib.md5(std['standard_id'].encode()).hexdigest()[:8], 16)
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=std
                )
            )
            
            # Progress indicator
            if i % 10 == 0 or i == len(ICSE_ISC_STANDARDS):
                print(f"  Progress: {i}/{len(ICSE_ISC_STANDARDS)} ({i/len(ICSE_ISC_STANDARDS)*100:.1f}%)")
            
            # Insert in batches
            if len(points) >= batch_size:
                client.upsert(collection_name=collection_name, points=points)
                points = []
                
        except Exception as e:
            print(f"❌ Error processing {std['standard_id']}: {e}")
    
    # Insert remaining points
    if points:
        client.upsert(collection_name=collection_name, points=points)
    
    print(f"\n✅ Successfully seeded {len(ICSE_ISC_STANDARDS)} standards!")
    
    # Get statistics
    info = client.get_collection(collection_name)
    print(f"\n📊 Collection Statistics:")
    print(f"   Total standards: {info.points_count}")
    print(f"   Vector dimensions: {info.config.params.vectors.size}")
    
    # Test retrieval
    print("\n🔍 Testing retrieval for 'photosynthesis' in Grade 9 Science...")
    query_response = openai_client.embeddings.create(
        input="photosynthesis",
        model="text-embedding-3-small"
    )
    query_vector = query_response.data[0].embedding
    
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(key="subject", match=MatchValue(value="Biology")),
                FieldCondition(key="grade", match=MatchValue(value="9"))
            ]
        ),
        limit=3
    ).points
    
    for hit in results:
        print(f"\n   [{hit.payload['standard_id']}] (Score: {hit.score:.3f})")
        print(f"   {hit.payload['text']}")
    
    print("\n✨ RAG service is ready! You can now generate lessons aligned with ISC/ICSE standards.")

if __name__ == "__main__":
    asyncio.run(seed_curriculum_standards())
