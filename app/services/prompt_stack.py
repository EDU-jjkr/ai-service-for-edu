from dataclasses import dataclass

from app.services.prompt_policy import concise_output_policy, deck_question_policy, json_only_policy


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str


def build_lesson_planner_prompt(
    *,
    topic: str,
    subject: str,
    grade_level: str,
    chapter: str | None,
    pedagogy_flow: str,
    additional_instructions: str | None,
) -> PromptBundle:
    system_prompt = "\n".join([
        "You are a lesson narrative planner for classroom-ready decks.",
        concise_output_policy(max_bullets=5, max_sentences=2),
        "Plan the lesson first. Do not write final slide prose.",
    ])
    user_prompt = "\n".join([
        f"topic: {topic}",
        f"subject: {subject}",
        f"grade_level: {grade_level}",
        f"chapter: {chapter or 'none'}",
        f"pedagogy_flow: {pedagogy_flow}",
        f"additional_instructions: {additional_instructions or 'none'}",
    ])
    return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)


def build_slide_author_prompt(
    *,
    topic: str,
    subject: str,
    grade_level: str,
    pedagogical_role: str,
    instructional_goal: str,
) -> PromptBundle:
    system_prompt = "\n".join([
        "You are a slide author working from a completed lesson plan.",
        concise_output_policy(max_bullets=5, max_sentences=2),
        deck_question_policy(),
        "Do not plan the full lesson again. Author only the requested slide.",
    ])
    user_prompt = "\n".join([
        f"topic: {topic}",
        f"subject: {subject}",
        f"grade_level: {grade_level}",
        f"pedagogical_role: {pedagogical_role}",
        f"instructional_goal: {instructional_goal}",
    ])
    return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)


def build_visual_intent_prompt(
    *,
    slide_title: str,
    pedagogical_role: str,
    content_mode: str,
    subject: str,
) -> PromptBundle:
    system_prompt = "\n".join([
        "You are a visual-intent director for educational slides.",
        json_only_policy(),
        "Choose instructional visuals before decorative visuals unless the slide is a hook.",
    ])
    user_prompt = "\n".join([
        f"slide_title: {slide_title}",
        f"pedagogical_role: {pedagogical_role}",
        f"content_mode: {content_mode}",
        f"subject: {subject}",
    ])
    return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)
