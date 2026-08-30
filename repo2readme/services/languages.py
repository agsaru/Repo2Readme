"""Detailed language analysis for a repository.

Breaks down file counts, line counts, byte sizes, and per-file listings
for every language detected in the project. Pure static analysis — no
API keys required.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from repo2readme.utils.detect_language import detect_lang


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FileLanguageInfo:
    """Per-file language metrics."""

    file_path: str
    relative_path: str
    language: str
    size_bytes: int
    line_count: int

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024.0


@dataclass
class LanguageBreakdown:
    """Aggregated metrics for a single language."""

    name: str
    file_count: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    files: list[FileLanguageInfo] = field(default_factory=list)

    @property
    def total_kb(self) -> float:
        return self.total_bytes / 1024.0

    @property
    def avg_lines_per_file(self) -> float:
        return self.total_lines / self.file_count if self.file_count else 0.0


@dataclass
class LanguageAnalysis:
    """Complete language analysis for a repository."""

    total_files: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    languages: dict[str, LanguageBreakdown] = field(default_factory=dict)

    def sorted_by_lines(self) -> list[LanguageBreakdown]:
        """Languages sorted by total lines, descending."""
        return sorted(self.languages.values(), key=lambda lb: lb.total_lines, reverse=True)

    def sorted_by_files(self) -> list[LanguageBreakdown]:
        """Languages sorted by file count, descending."""
        return sorted(self.languages.values(), key=lambda lb: lb.file_count, reverse=True)

    def top_languages(self, n: int = 5) -> list[LanguageBreakdown]:
        """Top N languages by line count."""
        return self.sorted_by_lines()[:n]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_languages(documents: list[dict]) -> LanguageAnalysis:
    """Analyze the languages used across all loaded documents.

    Parameters
    ----------
    documents:
        List of dicts with ``content`` and ``metadata`` keys, as produced
        by the traversal pipeline.

    Returns
    -------
    LanguageAnalysis
        A fully-populated analysis object.
    """
    analysis = LanguageAnalysis()
    breakdowns: dict[str, LanguageBreakdown] = {}

    for doc in documents:
        meta = doc.get("metadata", {})
        content = doc.get("content", "")
        file_path = meta.get("file_path", "")
        relative_path = meta.get("relative_path", "")

        if not file_path:
            continue

        language = meta.get("language") or detect_lang(file_path, content)
        size_bytes = len(content.encode("utf-8")) if isinstance(content, str) else 0
        line_count = len(content.splitlines()) if isinstance(content, str) else 0

        info = FileLanguageInfo(file_path, relative_path, language, size_bytes, line_count)

        if language not in breakdowns:
            breakdowns[language] = LanguageBreakdown(name=language)
        bd = breakdowns[language]
        bd.file_count += 1
        bd.total_lines += line_count
        bd.total_bytes += size_bytes
        bd.files.append(info)

        analysis.total_files += 1
        analysis.total_lines += line_count
        analysis.total_bytes += size_bytes

    analysis.languages = breakdowns
    return analysis


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def distribution_bar(breakdown: LanguageBreakdown, total_lines: int, width: int = 30) -> str:
    """Render a language's proportion as a text bar."""
    if total_lines == 0:
        return ""
    pct = breakdown.total_lines / total_lines
    filled = int(pct * width)
    empty = width - filled
    return f"{'#' * filled}{'.' * empty}"


def format_percentage(count: int, total: int) -> str:
    """Format a count as a percentage string."""
    if total == 0:
        return "0.0%"
    return f"{count / total * 100:.1f}%"


def format_byte_size(size_bytes: int) -> str:
    """Human-readable byte size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
