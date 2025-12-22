from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import Optional
from app.models.schemas import (
    DoubtRequest,
    DoubtResponse,
    FollowUpRequest,
    FollowUpResponse
)
from app.services.openai_service import generate_json_completion, generate_completion

router = APIRouter()

@router.post("/solve-doubt/text", response_model=DoubtResponse)
async def solve_text_doubt(request: DoubtRequest):
    """Solve a student doubt from text input"""
    try:
        # Build grade-appropriate context
        grade_context = f"Grade Level: {request.gradeLevel}" if request.gradeLevel else "general student"
        subject_context = f"Subject: {request.subject}" if request.subject else "subject to be identified"
        
        system_message = """You are an exceptional tutor with a gift for making complex concepts clear and accessible. You combine the patience of a great teacher with deep subject expertise across all academic disciplines.

Your tutoring philosophy:
- NEVER just give answers - always guide students to understand WHY
- Use the Socratic method: ask guiding questions that lead students to insights
- Break complex problems into manageable steps
- Celebrate the learning process, not just correct answers
- Address misconceptions gently and constructively
- Adapt explanations to student's grade level and prior knowledge
- Use analogies, examples, and visuals (described) when helpful
- Encourage growth mindset: mistakes are learning opportunities

Your explanations are known for:
- Crystal-clear step-by-step breakdowns
- Connecting new concepts to what students already know
- Practical examples from real life
- Identifying and addressing common misconceptions
- Building confidence while maintaining rigor

You NEVER do homework for students - instead, you teach them HOW to solve problems independently.

Always respond with valid, well-structured JSON."""

        prompt = f"""A student needs help with the following question:

STUDENT QUESTION: "{request.question}"

CONTEXT:
- {subject_context}
- {grade_context}

YOUR TASK: Provide tutoring that promotes deep understanding, not just surface answers.

TUTORING FRAMEWORK:

1. UNDERSTAND THE QUESTION:
   - Identify the core concept(s) being tested
   - Determine what the student needs to know to solve this
   - Identify the subject if not provided (be specific: "Algebra", not just "Math")
   - Consider common misconceptions for this type of problem

2. DIAGNOSTIC ASSESSMENT:
   - What prerequisite knowledge does this require?
   - What's the likely stumbling block for a {grade_context} student?
   - Is this a conceptual question or procedural problem?

3. BUILD THE SOLUTION (step-by-step):

   **Step-by-step Solution Structure:**
   
   a) START WITH THE "WHY":
      - Begin with 1-2 sentences explaining what concept this question addresses
      - Connect to something familiar if possible
   
   b) IDENTIFY WHAT WE KNOW:
      - List the given information clearly
      - Define any key terms or variables
   
   c) PLAN THE APPROACH:
      - Briefly outline the strategy (1-2 sentences)
      - "To solve this, we need to..."
   
   d) SOLVE STEP-BY-STEP:
      - Break into 3-7 clear, numbered steps
      - Each step should:
        * State what we're doing and WHY
        * Show the work/calculation/reasoning
        * Explain the result
      - Use formatting: **bold** for key terms, separate lines for calculations
      - Include "💡 Tip:" or "⚠️ Common Mistake:" callouts where relevant
   
   e) VERIFY THE ANSWER:
      - Check if the answer makes sense
      - Use estimation or logic to validate
   
   f) SUMMARIZE THE KEY INSIGHT:
      - End with 1-2 sentences about what we learned
      - "The key takeaway is..."

4. IDENTIFY RELATED CONCEPTS (3-4 concepts):
   - List foundational concepts this builds on
   - List advanced concepts this leads to
   - Make them specific, not generic (e.g., "Pythagorean Theorem" not "geometry")

5. CREATE PRACTICE PROBLEMS (2-3 similar problems):
   - Should test the SAME concept but with different numbers/context
   - Progress in difficulty: first slightly easier, last slightly harder
   - Include enough detail that problems are solvable
   - Make them interesting/relevant when possible

ADAPTATION FOR {grade_context}:
- Use vocabulary appropriate for this grade
- Reference concepts they'd know at this level
- Adjust complexity and depth of explanation accordingly
- For elementary: simple language, concrete examples
- For middle school: introduce abstract thinking gradually
- For high school: can use technical terms but explain them
- For college: assume more background, focus on nuance

OUTPUT FORMAT (return as JSON):
{{
    "question": "Restate the student's question clearly",
    "solution": "# Understanding the Question

[1-2 sentences: what concept does this address?]

## What We Know
• Given information point 1
• Given information point 2

## Our Approach
[Brief strategy statement]

## Step-by-Step Solution

**Step 1: [Action]**
[Explanation of what and why]
Calculation or reasoning here
Result: [what we found]

**Step 2: [Next Action]**
[Continue with clear steps]

💡 **Tip:** [Helpful insight or shortcut]

**Step 3: [Continue...]**
[More steps as needed]

⚠️ **Common Mistake:** [Address likely error]

## Checking Our Answer
[Verification reasoning]

## Key Takeaway
[1-2 sentences summarizing the important concept]",
    
    "subject": "Specific subject area (e.g., 'Algebra I', 'Biology - Cell Structure', 'World History')",
    
    "relatedConcepts": [
        "Foundational Concept 1 (builds on this)",
        "Core Concept 2 (directly related)",
        "Advanced Concept 3 (leads to this)",
        "Connected Concept 4 (also uses this)"
    ],
    
    "similarProblems": [
        "Problem 1: [Similar problem, slightly easier, with full context and specifics]",
        "Problem 2: [Similar problem, comparable difficulty, different scenario]",
        "Problem 3: [Similar problem, slightly harder, adds complexity]"
    ]
}}

CRITICAL QUALITY STANDARDS:
- Solution must be educational, not just correct
- Every step must include reasoning (the "why"), not just calculations
- Language and complexity must match {grade_context}
- Encourage independent thinking: "Can you see why...?" "Notice how..."
- No sarcasm or condescension - always respectful and encouraging
- Practice problems must be substantive and solvable
- Related concepts should create a learning pathway
- If this appears to be homework, focus on teaching METHOD not giving the answer

TUTORING MINDSET:
✓ Guide, don't just tell
✓ Build understanding, don't just provide answers
✓ Encourage curiosity and deeper questions
✓ Celebrate the learning process
✓ Make connections to broader concepts
✓ Empower students to solve similar problems independently

Generate the complete tutoring response now. Make it clear, encouraging, and genuinely educational."""

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=2800,  # Increased for detailed explanations
            temperature=0.6   # Lower for more consistent pedagogical quality
        )

        return DoubtResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to solve doubt: {str(e)}")


@router.post("/solve-doubt/image")
async def solve_image_doubt(
    image: UploadFile = File(...),
    subject: Optional[str] = Form(None),
    gradeLevel: Optional[str] = Form(None)
):
    """Solve a student doubt from an uploaded image (requires OCR integration)"""
    try:
        # TODO: Implement Google Cloud Vision OCR or similar
        # Once implemented, extract text and call solve_text_doubt logic
        
        raise HTTPException(
            status_code=501,
            detail="Image OCR integration pending. Please use text input for now."
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")


@router.post("/solve-doubt/voice")
async def solve_voice_doubt(
    audio: UploadFile = File(...),
    subject: Optional[str] = Form(None),
    gradeLevel: Optional[str] = Form(None)
):
    """Solve a student doubt from voice input (requires Whisper integration)"""
    try:
        # TODO: Implement OpenAI Whisper or similar speech-to-text
        # Once implemented, transcribe and call solve_text_doubt logic
        
        raise HTTPException(
            status_code=501,
            detail="Voice transcription integration pending. Please use text input for now."
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process audio: {str(e)}")


@router.post("/doubt/follow-up", response_model=FollowUpResponse)
async def answer_follow_up(request: FollowUpRequest):
    """Answer a follow-up question to a previous doubt"""
    try:
        system_message = """You are a patient, encouraging tutor in an ongoing conversation with a student. They've already received an explanation and now have a follow-up question.

Your approach:
- Treat this as a natural teaching dialogue
- Reference the previous explanation to build continuity
- Celebrate that they're asking follow-up questions (shows engagement!)
- If they're confused, try a different explanation approach
- If they want to go deeper, provide that advanced insight
- Maintain the same supportive, educational tone
- Never make students feel bad for not understanding

Always respond with valid JSON."""

        prompt = f"""You're continuing a tutoring session with a student.

ORIGINAL QUESTION: 
{request.originalQuestion}

PREVIOUS CONTEXT/EXPLANATION:
{request.previousContext if request.previousContext else "Initial explanation was provided"}

STUDENT'S FOLLOW-UP QUESTION:
"{request.followUpQuestion}"

ANALYZE THE FOLLOW-UP:
- Is this asking for clarification of something confusing?
- Is this asking to go deeper into the concept?
- Is this asking about a related concept?
- Is this revealing a misconception?

YOUR RESPONSE SHOULD:

1. ACKNOWLEDGE THE QUESTION POSITIVELY:
   - "Great question!" or "I'm glad you're asking about this" or "This is an important point"
   - Show that follow-up questions are valued

2. PROVIDE A CLEAR, TARGETED ANSWER:
   - Address the specific follow-up directly
   - Build on what was already explained
   - Use a different explanation approach if they're still confused
   - Add examples if helpful
   - Keep it concise but thorough

3. CONNECT BACK TO THE MAIN CONCEPT:
   - Show how this relates to the original question
   - Reinforce key learning points

4. CHECK FOR UNDERSTANDING:
   - End with an invitation for more questions if needed
   - Or provide a small thought prompt to check understanding

OUTPUT FORMAT (return as JSON):
{{
    "answer": "## Great follow-up question!

[Direct answer to their specific question, building on previous explanation]

[Use examples, analogies, or different explanation approach if needed]

[Connect back to main concept]

[Optional: Small thought prompt or invitation for more questions]",
    
    "clarification": "[Optional: Additional context, common confusion addressed, or advanced insight if they're ready for it]"
}}

RESPONSE GUIDELINES:
- Be conversational and encouraging
- Match the student's level from original context
- If they're confused, try explaining differently (new analogy, example, or approach)
- If they want depth, provide it without overwhelming
- Keep focused on their specific follow-up
- Max 2-3 paragraphs unless complexity requires more
- Maintain supportive tone: learning is a process

Generate the follow-up response now. Make it helpful, encouraging, and precisely targeted to their question."""

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=1800,  # Increased for thorough follow-ups
            temperature=0.7   # Maintain conversational warmth
        )

        return FollowUpResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to answer follow-up: {str(e)}")