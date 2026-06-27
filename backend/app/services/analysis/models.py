"""Analysis data models — plain dataclasses for pipeline results.

These are the structured outputs of each analysis step, culminating in
AnalysisContext which is the single object passed to the Agent Orchestrator
in Stage 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChangedFile:
    """A single file changed in a pull request."""

    filename: str  # e.g. "src/utils/parser.py"
    status: str  # "added" | "modified" | "removed" | "renamed"
    patch: str  # unified diff text for this file
    content: str | None  # full file content (None if deleted)


@dataclass
class PRIngestionResult:
    """Structured output from the ingestion service."""

    repo_full_name: str  # e.g. "owner/repo-name"
    pr_number: int
    pr_title: str
    base_branch: str  # e.g. "main"
    head_branch: str  # e.g. "feature/fix-parser"
    head_sha: str  # commit SHA of the PR head
    diff_text: str  # full PR unified diff
    changed_files: list[ChangedFile]


@dataclass
class ASTSymbol:
    """A single symbol extracted from an AST parse."""

    name: str  # symbol name
    type: str  # "function" | "class" | "import" | "async_function"
    line: int  # line number in source
    args: list[str] = field(default_factory=list)  # function arg names


@dataclass
class ASTSummary:
    """AST parse result for a single Python file."""

    filename: str
    symbols: list[ASTSymbol] = field(default_factory=list)
    parse_error: str | None = None  # None if parsing succeeded


@dataclass
class CallGraphResult:
    """Call/dependency graph scoped to changed files + 1-hop neighbors."""

    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


@dataclass
class LintFinding:
    """A single lint issue found by ruff."""

    file: str
    line: int
    column: int
    rule: str  # e.g. "F841"
    message: str  # human-readable description
    severity: str = "warning"  # "error" | "warning"


@dataclass
class TestResult:
    """Aggregated test execution results."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    total: int = 0
    tracebacks: list[str] = field(default_factory=list)
    timed_out: bool = False


@dataclass
class AnalysisContext:
    """Combined output of the full static analysis pipeline.

    This is the single object passed to the Agent Orchestrator in Stage 3.
    """

    ingestion: PRIngestionResult
    ast_summaries: list[ASTSummary] = field(default_factory=list)
    call_graph: CallGraphResult = field(default_factory=CallGraphResult)
    lint_findings: list[LintFinding] = field(default_factory=list)
    test_result: TestResult | None = None
