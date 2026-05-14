from __future__ import annotations

from apps.ai.workflows.generation.nodes import (
    brain_resolver,
    capacity_check,
    context_retrieval,
    draft_quality_gate,
    draft_repair,
    draft_schema_validator,
    intent_normalizer,
    persist_ready_for_review,
    quality_repair,
    repository_memory_search,
    request_gate,
    requirement_extraction,
    test_critic,
    test_design_generator,
)
from apps.ai.workflows.generation.state import TestGenerationState


def build_test_generation_graph():
    """Build the thin LangGraph wrapper for Step 4A offline generation."""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(TestGenerationState)
    graph.add_node("request_gate", request_gate)
    graph.add_node("brain_resolver", brain_resolver)
    graph.add_node("capacity_check", capacity_check)
    graph.add_node("context_retrieval", context_retrieval)
    graph.add_node("repository_memory_search", repository_memory_search)
    graph.add_node("intent_normalizer", intent_normalizer)
    graph.add_node("requirement_extraction", requirement_extraction)
    graph.add_node("test_design_generator", test_design_generator)
    graph.add_node("draft_schema_validator", draft_schema_validator)
    graph.add_node("draft_repair", draft_repair)
    graph.add_node("draft_quality_gate", draft_quality_gate)
    graph.add_node("quality_repair", quality_repair)
    graph.add_node("test_critic", test_critic)
    graph.add_node("persist_ready_for_review", persist_ready_for_review)

    graph.set_entry_point("request_gate")
    graph.add_edge("request_gate", "brain_resolver")
    graph.add_edge("brain_resolver", "capacity_check")
    graph.add_edge("capacity_check", "context_retrieval")
    graph.add_edge("context_retrieval", "repository_memory_search")
    graph.add_edge("repository_memory_search", "intent_normalizer")
    graph.add_edge("intent_normalizer", "requirement_extraction")
    graph.add_edge("requirement_extraction", "test_design_generator")
    graph.add_edge("test_design_generator", "draft_schema_validator")
    graph.add_edge("draft_schema_validator", "draft_repair")
    graph.add_edge("draft_repair", "draft_quality_gate")
    graph.add_edge("draft_quality_gate", "quality_repair")
    graph.add_edge("quality_repair", "test_critic")
    graph.add_edge("test_critic", "persist_ready_for_review")
    graph.add_edge("persist_ready_for_review", END)
    return graph.compile()


def run_test_generation_graph(state: TestGenerationState) -> TestGenerationState:
    return build_test_generation_graph().invoke(state)
