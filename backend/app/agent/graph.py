"""LangGraph graph construction and wiring.

Builds the Analyze -> Propose -> Verify -> Decide graph with a conditional
retry edge from Decide back to Analyze.

Graph topology:
    START -> analyze -> propose -> verify -> decide -> END (or -> analyze for retry)
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from app.agent.llm_client import BaseLLMClient
from app.agent.nodes import create_nodes
from app.agent.state import AgentState
from app.services.analysis.models import AnalysisContext

logger = logging.getLogger(__name__)


def build_agent_graph(llm_client: BaseLLMClient) -> StateGraph:
    """Build and compile the agent graph with the given LLM client.

    Args:
        llm_client: The LLM client to use (real or mock).

    Returns:
        A compiled LangGraph StateGraph.
    """
    nodes = create_nodes(llm_client)

    builder = StateGraph(AgentState)

    # Add the four nodes
    builder.add_node("analyze", nodes["analyze"])
    builder.add_node("propose", nodes["propose"])
    builder.add_node("verify", nodes["verify"])
    builder.add_node("decide", nodes["decide"])

    # Linear edges: START -> analyze -> propose -> verify -> decide
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", "propose")
    builder.add_edge("propose", "verify")
    builder.add_edge("verify", "decide")

    # Conditional edge from decide: retry or finalize
    def should_retry(state: AgentState) -> str:
        if state["decision"] == "pending":
            return "analyze"  # retry loop
        return END  # finalize (accepted or needs_human_review)

    builder.add_conditional_edges(
        "decide",
        should_retry,
        {"analyze": "analyze", END: END},
    )

    return builder.compile()


def _serialize_analysis_context(context: AnalysisContext) -> dict:
    """Convert AnalysisContext dataclass tree to a plain dict for LangGraph state.

    LangGraph state must be JSON-serializable. Dataclasses are converted
    via asdict(), which handles nested dataclasses recursively.
    """
    return asdict(context)


async def run_agent(
    analysis_context: AnalysisContext,
    work_dir: Path,
    llm_client: BaseLLMClient,
    max_retries: int = 3,
) -> AgentState:
    """Entry point: build graph, create initial state, invoke, return final state.

    Args:
        analysis_context: The AnalysisContext from Stage 2's static analysis.
        work_dir: Path to the original unmodified clone (preserved across retries).
        llm_client: The LLM client to use.
        max_retries: Maximum number of retry attempts before escalating.

    Returns:
        The final AgentState after the graph completes.
    """
    graph = build_agent_graph(llm_client)

    initial_state: AgentState = {
        "analysis_context": _serialize_analysis_context(analysis_context),
        "work_dir": str(work_dir),
        "diagnosis": "",
        "proposed_fix": "",
        "reasoning_text": "",
        "verification_passed": False,
        "verification_details": "",
        "retry_count": 0,
        "max_retries": max_retries,
        "confidence_score": 0.0,
        "decision": "pending",
        "node_trace": [],
    }

    logger.info(
        "Starting agent for %s PR #%s (max_retries=%d)",
        analysis_context.ingestion.repo_full_name,
        analysis_context.ingestion.pr_number,
        max_retries,
    )

    # Invoke the graph — LangGraph runs nodes until END is reached
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "Agent complete: decision=%s, confidence=%.2f, retries=%d, trace=%s",
        final_state["decision"],
        final_state["confidence_score"],
        final_state["retry_count"],
        final_state["node_trace"],
    )

    return final_state
