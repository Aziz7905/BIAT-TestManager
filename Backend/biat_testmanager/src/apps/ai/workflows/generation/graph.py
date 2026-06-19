from __future__ import annotations

from apps.ai.workflows.generation.nodes import (
    brain_resolver,
    capacity_check,
    finalize_generation,
    generation_planner,
    intent_normalizer,
    persist_clarification_required,
    plan_context_router,
    project_rag_context,
    repository_memory_search,
    repository_memory_gate,
    request_gate,
    requirement_extraction,
    route_after_context_router,
    route_after_generation_planner,
    route_after_repository_memory_gate,
    route_after_temporary_context,
    scenario_expand_loop,
    selected_spec_context,
    temporary_attachment_context,
)
from apps.ai.workflows.generation.state import TestGenerationState


def build_test_generation_graph():
    """Build the thin LangGraph wrapper for Step 4A offline generation."""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(TestGenerationState)
    graph.add_node("request_gate", request_gate)
    graph.add_node("brain_resolver", brain_resolver)
    graph.add_node("capacity_check", capacity_check)
    graph.add_node("plan_context_router", plan_context_router)
    graph.add_node("selected_spec_context", selected_spec_context)
    graph.add_node("temporary_attachment_context", temporary_attachment_context)
    graph.add_node("project_rag_context", project_rag_context)
    graph.add_node("repository_memory_gate", repository_memory_gate)
    graph.add_node("repository_memory_search", repository_memory_search)
    graph.add_node("intent_normalizer", intent_normalizer)
    graph.add_node("requirement_extraction", requirement_extraction)
    graph.add_node("generation_planner", generation_planner)
    graph.add_node("persist_clarification_required", persist_clarification_required)
    graph.add_node("scenario_expand_loop", scenario_expand_loop)
    graph.add_node("finalize_generation", finalize_generation)

    graph.set_entry_point("request_gate")
    graph.add_edge("request_gate", "brain_resolver")
    graph.add_edge("brain_resolver", "capacity_check")
    graph.add_edge("capacity_check", "plan_context_router")
    graph.add_conditional_edges(
        "plan_context_router",
        route_after_context_router,
        {
            "selected_spec_context": "selected_spec_context",
            "temporary_attachment_context": "temporary_attachment_context",
        },
    )
    graph.add_edge("selected_spec_context", "temporary_attachment_context")
    graph.add_conditional_edges(
        "temporary_attachment_context",
        route_after_temporary_context,
        {
            "project_rag_context": "project_rag_context",
            "repository_memory_gate": "repository_memory_gate",
        },
    )
    graph.add_edge("project_rag_context", "repository_memory_gate")
    graph.add_conditional_edges(
        "repository_memory_gate",
        route_after_repository_memory_gate,
        {
            "repository_memory_search": "repository_memory_search",
            "intent_normalizer": "intent_normalizer",
        },
    )
    graph.add_edge("repository_memory_search", "intent_normalizer")
    graph.add_edge("intent_normalizer", "requirement_extraction")
    graph.add_edge("requirement_extraction", "generation_planner")
    graph.add_conditional_edges(
        "generation_planner",
        route_after_generation_planner,
        {
            "persist_clarification_required": "persist_clarification_required",
            "scenario_expand_loop": "scenario_expand_loop",
        },
    )
    graph.add_edge("persist_clarification_required", END)
    graph.add_edge("scenario_expand_loop", "finalize_generation")
    graph.add_edge("finalize_generation", END)
    return graph.compile()


def run_test_generation_graph(state: TestGenerationState) -> TestGenerationState:
    return build_test_generation_graph().invoke(state)
