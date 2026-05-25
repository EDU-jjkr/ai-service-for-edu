from dataclasses import dataclass


DEFAULT_PEDAGOGY_FLOW = "default_classroom"


@dataclass(frozen=True)
class PedagogyFlow:
    flow_id: str
    cluster_order: tuple[str, ...]


FLOW_CATALOG = {
    "default_classroom": PedagogyFlow(
        flow_id="default_classroom",
        cluster_order=("hook", "explain", "example", "guided_practice", "independent_practice", "summary"),
    ),
    "problem_solving_math": PedagogyFlow(
        flow_id="problem_solving_math",
        cluster_order=("hook", "example", "guided_practice", "explain", "independent_practice", "summary"),
    ),
    "revision_exam_prep": PedagogyFlow(
        flow_id="revision_exam_prep",
        cluster_order=("hook", "explain", "guided_practice", "guided_practice", "summary"),
    ),
}


def normalize_pedagogy_flow(flow_id: str | None) -> str:
    candidate = (flow_id or "").strip().lower()
    if candidate in FLOW_CATALOG:
        return candidate
    return DEFAULT_PEDAGOGY_FLOW


def select_pedagogy_flow(
    *,
    subject: str,
    additional_instructions: str | None,
    requested_flow: str | None = None,
) -> PedagogyFlow:
    normalized_requested = (requested_flow or "").strip().lower()
    if normalized_requested in FLOW_CATALOG:
        return FLOW_CATALOG[normalized_requested]

    subject_key = (subject or "").strip().lower()
    instruction_text = (additional_instructions or "").lower()

    if "problem solving" in instruction_text and subject_key in {"mathematics", "math"}:
        return FLOW_CATALOG["problem_solving_math"]
    if "exam revision" in instruction_text or "revision deck" in instruction_text:
        return FLOW_CATALOG["revision_exam_prep"]
    return FLOW_CATALOG[DEFAULT_PEDAGOGY_FLOW]
