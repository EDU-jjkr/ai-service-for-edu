from typing import List, Dict, Any
from app.services.openai_service import generate_json_completion, stream_completion
from app.models.lesson_schema import BloomLevel, SlideType
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class OutlinerAgent:
    """
    Step 1: Creates a structural outline for the lesson.
    Input: Topic, Grade, Subject
    Output: JSON List of slide headers and objectives
    """
    
    @staticmethod
    async def create_outline(topic: str, subject: str, grade_level: str) -> List[Dict[str, str]]:
        """
        Create a curriculum-aligned outline using RAG with strict Bloom's Taxonomy progression.
        """
        from app.services.rag_service import get_curriculum_rag
        
        # Determine curriculum based on grade level
        grade_num = int(grade_level) if grade_level.isdigit() else 8
        curriculum = "ISC" if grade_num >= 11 else "ICSE"
        
        # Retrieve relevant curriculum standards
        try:
            rag = get_curriculum_rag()
            standards = await rag.retrieve_relevant_standards(
                topic=topic,
                subject=subject,
                grade=str(grade_num),
                curriculum=curriculum,
                top_k=3
            )
            
            if standards:
                standard_ids = [s['standard_id'] for s in standards]
                logger.info(f"✓ Aligned with standards: {', '.join(standard_ids)}")
        except Exception as e:
            logger.warning(f"RAG retrieval failed, proceeding without standards: {e}")
            standards = []
        
        # Enhanced system message with Bloom's Taxonomy instructions
        system_message = """You are an expert curriculum designer with deep knowledge of Bloom's Taxonomy.

CRITICAL: Design a lesson that STRICTLY follows Bloom's Taxonomy progression:
1. Start with REMEMBER (recall facts, define terms, list key points)
2. Progress to UNDERSTAND (explain, summarize, describe processes)
3. Move to APPLY (use knowledge in new situations, solve problems)
4. Advance to ANALYZE (compare, contrast, examine relationships)
5. Conclude with EVALUATE/CREATE (judge, critique, design, compose)

PEDAGOGICAL MODEL: Follow "I Do, We Do, You Do" structure with INTERLEAVED PRACTICE.

TOPIC DECOMPOSITION:
- If the topic is broad (e.g., "Gaseous Law of Motion"), automatically identify 3-4 key sub-topics
- Group slides logically around each sub-topic
- Example: "Gaseous Laws" -> Boyle's Law, Charles's Law, Gay-Lussac's Law, Avogadro's Law

For each slide, you MUST specify:
- title: Clear, specific slide title
- slideType: INTRODUCTION | CONCEPT | ACTIVITY | ASSESSMENT | SUMMARY
- bloom_level: REMEMBER | UNDERSTAND | APPLY | ANALYZE | EVALUATE | CREATE
- objective: Concrete, measurable learning objective

SLIDE TYPE GUIDELINES WITH MANDATORY PRACTICE:
- INTRODUCTION (1-2 slides): REMEMBER level - Define terms, introduce topic
- CONCEPT (3-5 slides): UNDERSTAND/APPLY levels - Explain concepts, show examples
- ACTIVITY (4-6 slides): APPLY/ANALYZE levels - Practice problems, comparisons
  * CRITICAL: Include at least 1-2 practice questions for EACH sub-topic identified
  * Every CONCEPT slide should be followed by an ACTIVITY slide with practice questions
- ASSESSMENT (3-4 slides): ANALYZE/EVALUATE levels - Critical thinking, evaluation
  * Include a "Final Challenge Round" with 3+ mixed questions covering all sub-topics
- SUMMARY (1 slide): CREATE level - Synthesize learning, propose solutions

Return a JSON object with a 'slides' key containing a list of slide outlines."""

        # Inject standards into system message if available
        if standards:
            system_message = rag.inject_into_prompt(standards, system_message)

        prompt = f"""Create a lesson outline for:
Topic: {topic}
Subject: {subject}
Grade: {grade_level}
Curriculum: {curriculum}

CRITICAL INSTRUCTION: If the topic is broad, first identify 3-4 key sub-topics and structure the lesson around them.

Generate 12-18 slides that progress through Bloom's Taxonomy levels with INTERLEAVED PRACTICE.

For each slide provide:
- 'title': The slide title
- 'slideType': One of ['INTRODUCTION', 'CONCEPT', 'ACTIVITY', 'ASSESSMENT', 'SUMMARY']
- 'bloom_level': One of ['REMEMBER', 'UNDERSTAND', 'APPLY', 'ANALYZE', 'EVALUATE', 'CREATE']
- 'objective': Specific, measurable learning objective

EXAMPLE PROGRESSION (15 slides with interleaved practice):
{{
  "slides": [
    {{"title": "What is {topic}?", "slideType": "INTRODUCTION", "bloom_level": "REMEMBER", "objective": "Define {topic} and identify key terms"}},
    {{"title": "Sub-Topic 1: Overview", "slideType": "CONCEPT", "bloom_level": "UNDERSTAND", "objective": "Explain the first key concept"}},
    {{"title": "Sub-Topic 1: Practice Questions", "slideType": "ACTIVITY", "bloom_level": "APPLY", "objective": "Solve problems related to first concept"}},
    {{"title": "Sub-Topic 2: Overview", "slideType": "CONCEPT", "bloom_level": "UNDERSTAND", "objective": "Explain the second key concept"}},
    {{"title": "Sub-Topic 2: Practice Questions", "slideType": "ACTIVITY", "bloom_level": "APPLY", "objective": "Solve problems related to second concept"}},
    {{"title": "Sub-Topic 3: Overview", "slideType": "CONCEPT", "bloom_level": "UNDERSTAND", "objective": "Explain the third key concept"}},
    {{"title": "Sub-Topic 3: Practice Questions", "slideType": "ACTIVITY", "bloom_level": "APPLY", "objective": "Solve problems related to third concept"}},
    {{"title": "Comparing All Sub-Topics", "slideType": "ACTIVITY", "bloom_level": "ANALYZE", "objective": "Compare and contrast different concepts"}},
    {{"title": "Critical Analysis Question", "slideType": "ASSESSMENT", "bloom_level": "ANALYZE", "objective": "Analyze relationships and patterns"}},
    {{"title": "Evaluation Question", "slideType": "ASSESSMENT", "bloom_level": "EVALUATE", "objective": "Judge effectiveness and limitations"}},
    {{"title": "Final Challenge Round", "slideType": "ASSESSMENT", "bloom_level": "EVALUATE", "objective": "Solve 3+ mixed questions covering all sub-topics"}},
    {{"title": "Summary & Key Takeaways", "slideType": "SUMMARY", "bloom_level": "CREATE", "objective": "Synthesize learning and propose solutions"}}
  ]
}}

MANDATORY REQUIREMENTS:
- Identify sub-topics if the main topic is broad
- Include at least 1-2 practice questions for EACH sub-topic
- Include a \"Final Challenge Round\" assessment with 3+ mixed questions
- Ensure smooth Bloom's Taxonomy progression"""

        try:
            result = await generate_json_completion(
                prompt=prompt,
                system_message=system_message,
                max_tokens=1200
            )
            
            slides = result.get("slides", [])
            
            # Validate Bloom's progression
            OutlinerAgent._validate_bloom_progression(slides)
            
            return slides
            
        except Exception as e:
            logger.error(f"Outliner failed: {e}")
            # Fallback outline with Bloom's progression
            return [
                {"title": f"Introduction to {topic}", "slideType": "INTRODUCTION", "bloom_level": "REMEMBER", "objective": "Define key terms"},
                {"title": "Key Concepts", "slideType": "CONCEPT", "bloom_level": "UNDERSTAND", "objective": "Explain main ideas"},
                {"title": "Application", "slideType": "ACTIVITY", "bloom_level": "APPLY", "objective": "Apply knowledge"},
                {"title": "Summary", "slideType": "SUMMARY", "bloom_level": "CREATE", "objective": "Synthesize learning"}
            ]
    
    @staticmethod
    def _validate_bloom_progression(slides: List[Dict]) -> None:
        """
        Validate that slides follow Bloom's Taxonomy progression.
        Logs warnings if progression is violated but doesn't fail.
        """
        bloom_order = ["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"]
        
        for i in range(1, len(slides)):
            prev_level = slides[i-1].get('bloom_level', 'UNDERSTAND')
            curr_level = slides[i].get('bloom_level', 'UNDERSTAND')
            
            try:
                prev_idx = bloom_order.index(prev_level)
                curr_idx = bloom_order.index(curr_level)
                
                # Allow staying at same level or progressing, but warn on regression
                if curr_idx < prev_idx - 1:
                    logger.warning(
                        f"Bloom's regression detected at slide {i}: "
                        f"{prev_level} (level {prev_idx}) → {curr_level} (level {curr_idx})"
                    )
            except ValueError:
                logger.warning(f"Invalid Bloom's level at slide {i}: {curr_level}")

class ContentAgent:
    """
    Step 2: Generates content for a specific slide.
    """
    
    @staticmethod
    async def generate_slide_content(slide_outline: Dict[str, str], subject: str, grade_level: str):
        """
        Stream the content for a single slide.
        Yields chunks of the generated content string.
        """
        # Check if this is a science/physics subject that needs detailed explanations
        is_science = any(kw in subject.lower() for kw in ['physics', 'chemistry', 'science', 'biology'])
        
        system_message = f"""You are an expert teacher for Grade {grade_level} {subject}.
Write COMPREHENSIVE teaching content for a presentation slide.
This content will be used to actually TEACH students, so be thorough.
Do not include markdown for bolding (**), just plain text.

CONTENT REQUIREMENTS:
{"For physics/science topics, include:" if is_science else "Include:"}
• Clear conceptual explanations with real-world analogies
• Mathematical formulas with explanation of each variable/term
• Step-by-step derivations where applicable
• Physical significance and intuition behind equations
• Historical context and who discovered/proposed it
• Common misconceptions and how to avoid them
• Visual descriptions (describe diagrams that would help)

SPECIAL INSTRUCTION FOR EQUATIONS:
When presenting equations like Schrödinger Equation, wave functions, etc:
• Write the full equation clearly
• Explain what each symbol represents
• Explain the physical meaning in simple terms
• Give both time-dependent and time-independent forms if applicable
• Explain boundary conditions and constraints

SPECIAL INSTRUCTION FOR PRACTICE QUESTIONS:
If the slide type is ACTIVITY or ASSESSMENT, structure your content as:
• Question: [Clear question statement with context]
• Options: A) [...] B) [...] C) [...] D) [...] (if multiple choice)
• Answer: [Correct answer]
• Detailed Explanation: [Step-by-step explanation of the solution]
• Common Mistakes: [What students typically get wrong]

For non-question slides, provide comprehensive bullet points with explanations."""

        slide_type = slide_outline.get('slideType', slide_outline.get('type', 'CONCEPT'))
        bloom_level = slide_outline.get('bloom_level', 'UNDERSTAND')
        
        # Determine content depth based on slide type
        if slide_type == 'INTRODUCTION':
            content_guidance = """
Provide:
• Hook/engaging opening (interesting fact or question)
• Clear definition of the main concept
• Historical background (when, who, why)
• Why this topic matters/real-world relevance
• Overview of what will be covered
• Prerequisites the student should know"""
        elif slide_type == 'CONCEPT':
            content_guidance = """
Provide:
• Detailed explanation of the concept
• Mathematical formulation with full breakdown
• Physical meaning and intuition
• Real-world examples and applications
• Common misconceptions to address
• Connection to previously learned concepts
• Visual/diagram description for better understanding"""
        elif slide_type in ['ACTIVITY', 'ASSESSMENT']:
            content_guidance = """
Provide:
• Clear problem statement with all given information
• Step-by-step solution approach
• Complete worked solution
• Final answer clearly stated
• Explanation of key insights
• Tips for similar problems"""
        elif slide_type == 'SUMMARY':
            content_guidance = """
Provide:
• Key concepts covered (comprehensive list)
• Important equations to remember
• Key takeaways and insights
• How this connects to other topics
• Suggested further reading/exploration
• Quick revision points"""
        else:
            content_guidance = "Provide comprehensive content with 6-8 detailed points."
        
        prompt = f"""Write DETAILED teaching content for this slide:
Title: {slide_outline['title']}
Type: {slide_type}
Bloom's Level: {bloom_level}
Objective: {slide_outline['objective']}

{content_guidance}

Remember: This content will be used to TEACH students. Be thorough, clear, and educational.
Include enough detail that a teacher can use this to deliver a complete lesson on the topic."""

        async for chunk in stream_completion(prompt, system_message, max_tokens=800):
            yield chunk
    
    @staticmethod
    async def generate_all_slides_parallel(outline: List[Dict], subject: str, grade_level: str) -> List[Dict]:
        """
        Generate content for all slides in parallel using asyncio.gather().
        Includes text content, speaker notes, and image queries.
        
        Returns: List[Slide] with full content + metadata
        """
        from app.agents.visual_director_agent import VisualDirectorAgent
        
        async def generate_single_slide(slide_plan: Dict, index: int) -> Dict:
            """Generate complete content for a single slide."""
            try:
                # Generate text content
                content_chunks = []
                async for chunk in ContentAgent.generate_slide_content(
                    slide_outline=slide_plan,
                    subject=subject,
                    grade_level=grade_level
                ):
                    content_chunks.append(chunk)
                content = ''.join(content_chunks)
                
                # Generate speaker notes
                notes = await ContentAgent.generate_speaker_notes(
                    title=slide_plan.get('title', ''),
                    content=content,
                    bloom_level=slide_plan.get('bloom_level', 'UNDERSTAND'),
                    subject=subject
                )
                
                # Generate image query (skip for SUMMARY slides)
                image_query = None
                slide_type_str = slide_plan.get('slideType', slide_plan.get('type', 'CONCEPT'))
                bloom_level_str = slide_plan.get('bloom_level', 'UNDERSTAND')
                
                # Convert strings to enums
                try:
                    bloom_level_enum = BloomLevel[bloom_level_str] if isinstance(bloom_level_str, str) else bloom_level_str
                except (KeyError, TypeError):
                    bloom_level_enum = BloomLevel.UNDERSTAND
                
                try:
                    slide_type_enum = SlideType[slide_type_str] if isinstance(slide_type_str, str) else slide_type_str
                except (KeyError, TypeError):
                    slide_type_enum = SlideType.CONCEPT
                
                if slide_type_str != "SUMMARY":
                    try:
                        query_result = await VisualDirectorAgent.generate_image_query(
                            slide_content=content,
                            slide_title=slide_plan.get('title', ''),
                            bloom_level=bloom_level_enum,
                            subject=subject,
                            grade_level=grade_level,
                            slide_type=slide_type_enum
                        )
                        # Fixed: Use 'imageQuery' instead of 'query'
                        image_query = query_result.get('imageQuery')
                        logger.debug(f"Image query for slide {index} '{slide_plan.get('title', '')}': {image_query}")
                    except Exception as e:
                        logger.warning(
                            f"Image query generation failed for slide {index} "
                            f"(title: '{slide_plan.get('title', '')}', type: {slide_type_str}): {e}"
                        )
                
                return {
                    "title": slide_plan.get('title', f"Slide {index + 1}"),
                    "content": content,
                    "order": index,
                    "slideType": slide_type_str,
                    "bloom_level": slide_plan.get('bloom_level', 'UNDERSTAND'),
                    "speakerNotes": notes,
                    "imageQuery": image_query,
                    "objective": slide_plan.get('objective', '')
                }
                
            except Exception as e:
                logger.error(f"Failed to generate slide {index} ({{slide_plan.get('title')}}): {e}")
                # Return minimal slide on error with fallback content
                return {
                    "title": slide_plan.get('title', f"Slide {index + 1}"),
                    "content": "Content generation in progress. Please regenerate this slide.",
                    "order": index,
                    "slideType": slide_plan.get('slideType', slide_plan.get('type', 'CONCEPT')),
                    "bloom_level": slide_plan.get('bloom_level', 'UNDERSTAND'),
                    "speakerNotes": "",
                    "imageQuery": None,
                    "objective": slide_plan.get('objective', '')
                }
        
        # Parallel execution with asyncio.gather
        logger.info(f"Generating {len(outline)} slides in parallel...")
        tasks = [
            generate_single_slide(plan, i)
            for i, plan in enumerate(outline)
        ]
        
        slides = await asyncio.gather(*tasks)
        logger.info(f"✓ Generated {len(slides)} slides")
        
        return list(slides)
    
    @staticmethod
    async def generate_speaker_notes(title: str, content: str, bloom_level: str, subject: str) -> str:
        """
        Generate teacher-facing speaker notes for a slide.
        
        Args:
            title: Slide title
            content: Slide content (bullet points)
            bloom_level: Bloom's Taxonomy level
            subject: Subject area
            
        Returns:
            Speaker notes string (concise, ~100 words)
        """
        prompt = f"""Generate concise teacher notes for this slide:

Title: {title}
Content: {content}
Bloom's Level: {bloom_level}
Subject: {subject}

Include:
1. Key teaching points (2-3 sentences max)
2. One common student misconception to address
3. One suggested question or activity

Keep it under 100 words. Be specific and actionable."""

        system_message = """You are an experienced teacher creating instructor notes.
Focus on practical teaching tips that help deliver the lesson effectively.
Be concise and specific to the content."""

        try:
            # Use streaming but collect all chunks
            chunks = []
            async for chunk in stream_completion(
                prompt=prompt,
                system_message=system_message,
                max_tokens=200
            ):
                chunks.append(chunk)
            
            return ''.join(chunks).strip()
            
        except Exception as e:
            logger.error(f"Speaker notes generation failed: {e}")
            return f"Teaching tip: Focus on {bloom_level.lower()}-level skills when presenting this content."
