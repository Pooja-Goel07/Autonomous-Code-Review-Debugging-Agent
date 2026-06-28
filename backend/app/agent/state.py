"""LangGraph agent state definition.

Carries all data through the Analyze -> Propose -> Verify -> Decide loop.
Uses Annotated reducers where append semantics are needed.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    """State object flowing through the LangGraph agent loop.

    Fields are grouped by which node produces them.
    """

    # --- Input (set once before graph starts) ---
    analysis_context: dict  # AnalysisContext serialized as dict (LangGraph needs serializable state)
    work_dir: str  # path to the original unmodified clone (never written to)

    # --- Analyze node output ---
    diagnosis: str  # LLM's root cause analysis

    # --- Propose node output ---
    proposed_fix: str  # diff-style patch text or direct file replacement
    reasoning_text: str  # human-readable explanation of the fix

    # --- Verify node output ---
    verification_passed: bool  # True if tests pass after applying the fix
    verification_details: str  # test output summary

    # --- Decide node output / control flow ---
    retry_count: int  # current retry attempt (starts at 0)
    max_retries: int  # configurable cap (default 3)
    confidence_score: float  # 0.0 - 1.0
    decision: str  # "accepted" | "needs_human_review" | "pending"

    # --- Observability ---
    # Uses operator.add reducer so each node appends to the trace
    # instead of overwriting it. Nodes return {"node_trace": ["analyze"]}
    # and LangGraph concatenates onto the existing list.
    node_trace: Annotated[list[str], operator.add]
