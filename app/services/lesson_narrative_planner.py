from dataclasses import dataclass

from app.services.pedagogy_flows import DEFAULT_PEDAGOGY_FLOW, select_pedagogy_flow


@dataclass
class NarrativeCluster:
    kind: str
    slide_count: int
    subtopics: list[str]


@dataclass
class LessonNarrativePlan:
    clusters: list[NarrativeCluster]
    pedagogy_flow: str = DEFAULT_PEDAGOGY_FLOW


def _normalize_topics(topic: str | list[str]) -> list[str]:
    if isinstance(topic, list):
        return [str(item).strip() for item in topic if str(item).strip()]
    topic_value = str(topic).strip()
    return [topic_value] if topic_value else []


def build_lesson_narrative_plan(
    topic: str | list[str],
    subject: str,
    grade_level: str,
    chapter: str | None,
    additional_instructions: str | None,
    pedagogy_flow: str | None = None,
) -> LessonNarrativePlan:
    broad_subjects = {"physics", "chemistry", "biology", "mathematics", "math"}
    subject_key = (subject or "").strip().lower()
    topics = _normalize_topics(topic)
    if not topics:
        selected_flow = select_pedagogy_flow(
            subject=subject,
            additional_instructions=additional_instructions,
            requested_flow=pedagogy_flow,
        )
        return LessonNarrativePlan(clusters=[], pedagogy_flow=selected_flow.flow_id)

    try:
        grade_num = int(str(grade_level).strip())
    except (TypeError, ValueError):
        grade_num = 8

    explain_count = 3 if subject_key in broad_subjects else 2
    example_count = 2
    guided_count = 3 if subject_key in broad_subjects else 2

    if grade_num >= 11:
        explain_count += 1
        example_count += 1
    elif grade_num <= 5:
        explain_count = max(2, explain_count - 1)

    instruction_text = (additional_instructions or "").lower()
    if "extra practice" in instruction_text or "more practice" in instruction_text:
        guided_count += 1
    if "challenge" in instruction_text or "advanced" in instruction_text:
        guided_count += 1
        example_count += 1

    selected_flow = select_pedagogy_flow(
        subject=subject,
        additional_instructions=additional_instructions,
        requested_flow=pedagogy_flow,
    )

    slide_counts = {
        "hook": 1,
        "explain": explain_count,
        "example": example_count,
        "guided_practice": guided_count,
        "independent_practice": 1,
    }

    clusters: list[NarrativeCluster] = []
    for index, topic_name in enumerate(topics):
        hook_subtopic = chapter if chapter and len(topics) == 1 and index == 0 else topic_name
        for kind in selected_flow.cluster_order:
            if kind == "summary":
                continue
            subtopic = hook_subtopic if kind == "hook" else topic_name
            clusters.append(
                NarrativeCluster(
                    kind=kind,
                    slide_count=slide_counts.get(kind, 1),
                    subtopics=[subtopic],
                )
            )

    summary_subtopics = topics[:]
    if chapter:
        summary_subtopics.append(chapter)
    clusters.append(NarrativeCluster(kind="summary", slide_count=1, subtopics=summary_subtopics))

    return LessonNarrativePlan(clusters=clusters, pedagogy_flow=selected_flow.flow_id)
