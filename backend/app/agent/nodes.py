"""LangGraph agent nodes — the four steps of the review loop.

Analyze:  LLM diagnoses root cause from AnalysisContext
Propose:  LLM proposes a concrete fix (diff/patch)
Verify:   Deterministic — applies fix to a fresh copy and runs tests
Decide:   Rule-based — accept, retry, or escalate to human review

Safety invariant: the agent NEVER auto-merges or auto-edits code.
It only produces proposed fixes that are later posted as draft PR comments.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from app.agent.llm_client import BaseLLMClient
from app.agent.patch import apply_patch
from app.agent.state import AgentState
from app.services.analysis.test_runner import run_tests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_ANALYZE_SYSTEM = """\
You are an expert code reviewer and debugging agent. Your task is to diagnose
the root cause of issues found in a pull request.

You will be given:
- The PR diff (changed code)
- Lint findings (ruff output)
- Test failures (pytest output)
- A call graph showing function dependencies

Analyze the evidence and produce a concise root cause diagnosis. Focus on:
1. What the actual bug or issue is
2. Which specific lines/functions are responsible
3. Why the current code fails

Be specific and technical. Do not suggest fixes yet — only diagnose."""

_PROPOSE_SYSTEM = """\
You are an expert code reviewer and debugging agent. Based on the diagnosis
provided, propose a concrete fix for the identified issue.

Return your fix in the following format:

===FILE: <relative_path>===
<complete replacement file content>
===END_FILE===

You may include multiple ===FILE=== blocks if multiple files need changes.

Also include a brief human-readable explanation of what your fix does and why.
Format the explanation AFTER the file blocks, starting with "REASONING:".

Important constraints:
- Only modify what is necessary to fix the identified issue
- Do not add unrelated changes
- Preserve existing code style and conventions"""


def _build_analysis_prompt(state: AgentState) -> str:
    """Build the user prompt for the Analyze node from AnalysisContext."""
    ctx = state["analysis_context"]

    parts = ["## PR Information"]
    parts.append(f"Repository: {ctx.get('repo_full_name', 'unknown')}")
    parts.append(f"PR #{ctx.get('pr_number', '?')}: {ctx.get('pr_title', '?')}")

    # Diff
    parts.append("\n## Code Diff")
    parts.append(ctx.get("diff_text", "(no diff available)"))

    # Lint findings
    lint = ctx.get("lint_findings", [])
    if lint:
        parts.append("\n## Lint Findings")
        for lf in lint:
            parts.append(f"  [{lf['rule']}] {lf['file']}:{lf['line']} - {lf['message']}")

    # Test results
    test = ctx.get("test_result")
    if test:
        parts.append("\n## Test Results")
        parts.append(f"  Passed: {test.get('passed', 0)}, Failed: {test.get('failed', 0)}")
        for tb in test.get("tracebacks", []):
            parts.append(f"\n  Traceback:\n{tb}")

    # Call graph
    cg = ctx.get("call_graph", {})
    if cg.get("nodes"):
        parts.append("\n## Call Graph")
        parts.append(f"  Nodes: {len(cg['nodes'])}, Edges: {len(cg.get('edges', []))}")
        for edge in cg.get("edges", [])[:20]:  # limit for prompt size
            parts.append(f"  {edge[0]} -> {edge[1]}")

    # If this is a retry, include previous diagnosis for context
    if state.get("retry_count", 0) > 0 and state.get("diagnosis"):
        parts.append(f"\n## Previous Diagnosis (attempt {state['retry_count']})")
        parts.append(state["diagnosis"])
        parts.append("\nThe previous fix did not resolve the issue. Please re-analyze.")

    return "\n".join(parts)


def _build_propose_prompt(state: AgentState) -> str:
    """Build the user prompt for the Propose node."""
    ctx = state["analysis_context"]

    parts = ["## Diagnosis"]
    parts.append(state.get("diagnosis", "(no diagnosis)"))

    # Include original file contents so the LLM can produce full replacements
    parts.append("\n## Current File Contents")
    for cf in ctx.get("changed_files", []):
        if cf.get("content"):
            parts.append(f"\n### {cf['filename']}")
            parts.append(f"```python\n{cf['content']}\n```")

    if state.get("retry_count", 0) > 0 and state.get("proposed_fix"):
        parts.append("\n## Previous Fix Attempt (failed)")
        parts.append(state["proposed_fix"])
        parts.append("\nThis fix did not resolve the issue. Please propose a different fix.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Node factory — closes over the LLM client
# ---------------------------------------------------------------------------

def create_nodes(llm_client: BaseLLMClient) -> dict:
    """Create the four agent node functions, closing over the LLM client.

    Returns a dict of {name: async_function} for use with StateGraph.add_node().
    """

    async def analyze_node(state: AgentState) -> dict:
        """Analyze: diagnose root cause using LLM."""
        logger.info("=== ANALYZE NODE (attempt %d) ===", state.get("retry_count", 0))

        prompt = _build_analysis_prompt(state)
        diagnosis = await llm_client.generate(_ANALYZE_SYSTEM, prompt)

        logger.info("Diagnosis: %s", diagnosis[:200])
        return {
            "diagnosis": diagnosis,
            "node_trace": ["analyze"],
        }

    async def propose_node(state: AgentState) -> dict:
        """Propose: generate a concrete fix using LLM."""
        logger.info("=== PROPOSE NODE ===")

        prompt = _build_propose_prompt(state)
        response = await llm_client.generate(_PROPOSE_SYSTEM, prompt)

        # Split fix from reasoning
        if "REASONING:" in response:
            fix_part, reasoning_part = response.split("REASONING:", 1)
            proposed_fix = fix_part.strip()
            reasoning_text = reasoning_part.strip()
        else:
            proposed_fix = response.strip()
            reasoning_text = "Fix proposed by the agent."

        logger.info("Proposed fix length: %d chars", len(proposed_fix))
        return {
            "proposed_fix": proposed_fix,
            "reasoning_text": reasoning_text,
            "node_trace": ["propose"],
        }

    async def verify_node(state: AgentState) -> dict:
        """Verify: apply the fix to a fresh copy and run tests.

        NO LLM call — deterministic check only.
        Each attempt copies from the ORIGINAL unmodified work_dir.
        """
        logger.info("=== VERIFY NODE ===")

        original_work_dir = Path(state["work_dir"])
        verify_dir = Path(tempfile.mkdtemp(prefix="cr_verify_"))

        try:
            # Copy from the ORIGINAL clone (not a previous attempt's patched copy)
            shutil.copytree(original_work_dir, verify_dir, dirs_exist_ok=True)

            # Apply the proposed fix
            patch_ok = apply_patch(verify_dir, state.get("proposed_fix", ""))
            if not patch_ok:
                return {
                    "verification_passed": False,
                    "verification_details": "Failed to apply patch to files.",
                    "node_trace": ["verify"],
                }

            # Run tests in the patched copy
            test_result = await run_tests(verify_dir)

            passed = (
                test_result.passed > 0
                and test_result.failed == 0
                and test_result.errors == 0
                and not test_result.timed_out
            )

            details_parts = [
                f"Tests: {test_result.passed} passed, {test_result.failed} failed, "
                f"{test_result.errors} errors",
            ]
            if test_result.timed_out:
                details_parts.append("Test execution timed out.")
            if test_result.tracebacks:
                details_parts.append("Failures:")
                details_parts.extend(test_result.tracebacks)

            details = "\n".join(details_parts)
            logger.info("Verification: %s", "PASSED" if passed else "FAILED")

            return {
                "verification_passed": passed,
                "verification_details": details,
                "node_trace": ["verify"],
            }

        finally:
            # Clean up the verification copy
            shutil.rmtree(verify_dir, ignore_errors=True)

    async def decide_node(state: AgentState) -> dict:
        """Decide: accept, retry, or escalate. Rule-based, no LLM call."""
        logger.info("=== DECIDE NODE ===")

        verification_passed = state.get("verification_passed", False)
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)

        if verification_passed:
            # Tests pass — accept with high confidence
            decision = "accepted"
            confidence = 0.85
            logger.info("Decision: ACCEPTED (confidence=%.2f)", confidence)

        elif retry_count < max_retries:
            # Tests fail but retries remain — loop back
            decision = "pending"
            confidence = 0.0
            retry_count += 1
            logger.info(
                "Decision: RETRY (attempt %d/%d)", retry_count, max_retries
            )

        else:
            # Max retries exhausted — escalate to human
            decision = "needs_human_review"
            confidence = 0.2
            logger.info("Decision: NEEDS HUMAN REVIEW (max retries reached)")

        return {
            "decision": decision,
            "confidence_score": confidence,
            "retry_count": retry_count,
            "node_trace": ["decide"],
        }

    return {
        "analyze": analyze_node,
        "propose": propose_node,
        "verify": verify_node,
        "decide": decide_node,
    }
