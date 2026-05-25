from typing import Dict, List

VAGUE_CONTROL_TERMS = [
    "easy",
    "medium",
    "hard",
    "simple",
    "complex",
    "advanced",
    "basic",
    "professional",
    "comprehensive",
    "challenging",
    "high quality",
    "beautiful",
]


DIFFICULTY_PROFILES: Dict[str, Dict[str, str]] = {
    "foundation": {
        "step_count_range": "1-3 steps maximum",
        "prerequisite_depth": "self-contained and directly supported by the lesson",
        "concept_span": "single core concept",
        "cognitive_operation": "identify, recall, define, interpret",
        "expected_time_min": "under 5 minutes",
        "distractor_similarity": "plausible but separable using one correct fact",
    },
    "application": {
        "step_count_range": "4-7 steps",
        "prerequisite_depth": "foundational topic fluency expected",
        "concept_span": "2-3 linked concepts inside one topic",
        "cognitive_operation": "apply, compare, analyze, differentiate",
        "expected_time_min": "10-20 minutes",
        "distractor_similarity": "plausible alternatives based on common misconceptions",
    },
    "integrated": {
        "step_count_range": "8+ steps or multi-constraint reasoning",
        "prerequisite_depth": "deep mastery across multiple connected concepts",
        "concept_span": "cross-topic synthesis or competition-style transfer",
        "cognitive_operation": "justify, evaluate, synthesize, create",
        "expected_time_min": "30+ minutes",
        "distractor_similarity": "highly plausible alternatives requiring precise reasoning to reject",
    },
}


def difficulty_contract(profile_name: str) -> str:
    profile = DIFFICULTY_PROFILES[profile_name]
    return "\n".join([
        f"- step_count_range: {profile['step_count_range']}",
        f"- prerequisite_depth: {profile['prerequisite_depth']}",
        f"- concept_span: {profile['concept_span']}",
        f"- cognitive_operation: {profile['cognitive_operation']}",
        f"- expected_time: {profile['expected_time_min']}",
        f"- distractor_similarity: {profile['distractor_similarity']}",
    ])


def deck_question_policy() -> str:
    return f"""QUESTION DESIGN POLICY:
- Do not rely on vague labels such as easy, medium, hard, simple, complex, advanced, or comprehensive.
- Use the operative constraints below instead.

FOUNDATION CHECK:
{difficulty_contract("foundation")}

MULTI-STEP APPLICATION:
{difficulty_contract("application")}

INTEGRATED CHALLENGE:
{difficulty_contract("integrated")}"""


def concise_output_policy(max_bullets: int = 6, max_sentences: int = 2) -> str:
    return f"""OUTPUT BUDGET POLICY:
- Keep each slide focused on one teaching goal.
- Use at most {max_bullets} bullets on instructional slides.
- Keep each bullet to one sentence when possible.
- Keep explanation blocks to at most {max_sentences} sentences unless the slide is explicitly a worked solution.
- Prefer compact, observable constraints over style adjectives."""


def json_only_policy() -> str:
    return "\n".join([
        "JSON OUTPUT POLICY:",
        "- Return JSON only.",
        "- Do not include markdown fences or commentary outside the JSON payload.",
    ])


def find_vague_terms(text: str) -> List[str]:
    lowered = (text or "").lower()
    return [term for term in VAGUE_CONTROL_TERMS if term in lowered]
