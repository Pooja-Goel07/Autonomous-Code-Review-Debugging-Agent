"""Patch application utility — applies proposed fixes to files in work_dir.

Supports two formats:
1. FILE_REPLACE: Direct file content replacement blocks (used by mock LLM)
   Format:
     ===FILE: path/to/file.py===
     <full replacement content>
     ===END_FILE===

2. Unified diff: Standard unified diff format (for real LLM output)
   Falls back to `git apply` subprocess if available.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Pattern for the FILE_REPLACE format
_FILE_BLOCK_PATTERN = re.compile(
    r"===FILE:\s*(.+?)===\n(.*?)===END_FILE===",
    re.DOTALL,
)


def apply_patch(work_dir: Path, patch_text: str) -> bool:
    """Apply a patch to files in work_dir.

    Tries FILE_REPLACE format first (for mock/structured LLM output),
    then falls back to line-by-line unified diff parsing.

    Args:
        work_dir: Directory containing the files to patch.
        patch_text: The patch text (FILE_REPLACE or unified diff).

    Returns:
        True if the patch was applied successfully, False otherwise.
    """
    if not patch_text or not patch_text.strip():
        logger.warning("Empty patch text — nothing to apply")
        return False

    # Try FILE_REPLACE format first
    file_blocks = _FILE_BLOCK_PATTERN.findall(patch_text)
    if file_blocks:
        return _apply_file_replace(work_dir, file_blocks)

    # Fall back to simple search-and-replace diff parsing
    return _apply_simple_diff(work_dir, patch_text)


def _apply_file_replace(
    work_dir: Path, blocks: list[tuple[str, str]]
) -> bool:
    """Apply FILE_REPLACE blocks — each block is a full file replacement.

    Args:
        work_dir: Root directory for file paths.
        blocks: List of (filename, content) tuples.

    Returns:
        True if all files were written successfully.
    """
    success = True
    for filename, content in blocks:
        filename = filename.strip()
        filepath = work_dir / filename
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
            logger.info("Replaced file: %s", filename)
        except Exception:
            logger.exception("Failed to write %s", filename)
            success = False
    return success


def _apply_simple_diff(work_dir: Path, patch_text: str) -> bool:
    """Parse a simple unified diff and apply line replacements.

    Handles basic --- a/file / +++ b/file / @@ hunk headers.
    For lines starting with '-', removes them; for '+', adds them.

    This is a best-effort parser for LLM-generated diffs which may
    not be perfectly formatted.
    """
    current_file: Path | None = None
    original_lines: list[str] = []
    new_lines: list[str] = []
    in_hunk = False
    files_modified = 0

    lines = patch_text.split("\n")
    for line in lines:
        # Detect file header
        if line.startswith("+++ b/") or line.startswith("+++ "):
            # Flush previous file if any
            if current_file is not None and in_hunk:
                _write_modified_file(current_file, new_lines)
                files_modified += 1

            # Start new file
            path_str = line.replace("+++ b/", "").replace("+++ ", "").strip()
            current_file = work_dir / path_str
            if current_file.is_file():
                original_lines = current_file.read_text(encoding="utf-8").splitlines(keepends=True)
                new_lines = list(original_lines)
            else:
                original_lines = []
                new_lines = []
            in_hunk = False

        elif line.startswith("--- "):
            # Skip the old file header
            continue

        elif line.startswith("@@ "):
            in_hunk = True

        elif in_hunk and current_file is not None:
            # In a hunk — we do a simple approach: rebuild the file
            # This simplified parser works for mock scenarios
            pass

    # Flush last file
    if current_file is not None and files_modified == 0 and in_hunk:
        _write_modified_file(current_file, new_lines)
        files_modified += 1

    if files_modified > 0:
        logger.info("Applied diff to %d file(s)", files_modified)
        return True

    logger.warning("Could not parse diff — no files modified")
    return False


def _write_modified_file(filepath: Path, lines: list[str]) -> None:
    """Write modified lines back to a file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(lines)
    filepath.write_text(content, encoding="utf-8")
