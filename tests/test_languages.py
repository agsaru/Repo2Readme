"""Tests for repo2readme.services.languages — detailed language analysis."""

from __future__ import annotations

import pytest

from repo2readme.services.languages import (
    FileLanguageInfo,
    LanguageAnalysis,
    LanguageBreakdown,
    analyze_languages,
    distribution_bar,
    format_byte_size,
    format_percentage,
)


def _make_doc(content: str = "x = 1", file_path: str = "/repo/src/main.py",
              relative_path: str = "src/main.py", language: str | None = None) -> dict:
    meta = {"file_path": file_path, "relative_path": relative_path}
    if language:
        meta["language"] = language
    return {"content": content, "metadata": meta}


# ---------------------------------------------------------------------------
# FileLanguageInfo
# ---------------------------------------------------------------------------

class TestFileLanguageInfo:
    def test_size_kb(self):
        fi = FileLanguageInfo("/a.py", "a.py", "python", 2048, 50)
        assert fi.size_kb == 2.0

    def test_size_kb_small(self):
        fi = FileLanguageInfo("/a.py", "a.py", "python", 100, 5)
        assert fi.size_kb == pytest.approx(0.097, abs=0.01)


# ---------------------------------------------------------------------------
# LanguageBreakdown
# ---------------------------------------------------------------------------

class TestLanguageBreakdown:
    def test_avg_lines(self):
        lb = LanguageBreakdown("python", file_count=4, total_lines=200)
        assert lb.avg_lines_per_file == 50.0

    def test_avg_lines_zero_files(self):
        lb = LanguageBreakdown("python")
        assert lb.avg_lines_per_file == 0.0

    def test_total_kb(self):
        lb = LanguageBreakdown("python", total_bytes=5120)
        assert lb.total_kb == 5.0


# ---------------------------------------------------------------------------
# LanguageAnalysis
# ---------------------------------------------------------------------------

class TestLanguageAnalysis:
    def test_sorted_by_lines(self):
        a = LanguageAnalysis()
        a.languages = {
            "python": LanguageBreakdown("python", total_lines=500),
            "javascript": LanguageBreakdown("javascript", total_lines=200),
            "html": LanguageBreakdown("html", total_lines=100),
        }
        sorted_langs = a.sorted_by_lines()
        assert [lb.name for lb in sorted_langs] == ["python", "javascript", "html"]

    def test_sorted_by_files(self):
        a = LanguageAnalysis()
        a.languages = {
            "python": LanguageBreakdown("python", file_count=10),
            "js": LanguageBreakdown("js", file_count=20),
        }
        assert a.sorted_by_files()[0].name == "js"

    def test_top_languages(self):
        a = LanguageAnalysis()
        a.languages = {
            f"lang{i}": LanguageBreakdown(f"lang{i}", total_lines=(5 - i) * 100)
            for i in range(5)
        }
        top = a.top_languages(3)
        assert len(top) == 3
        assert top[0].name == "lang0"


# ---------------------------------------------------------------------------
# analyze_languages
# ---------------------------------------------------------------------------

class TestAnalyzeLanguages:
    def test_empty(self):
        result = analyze_languages([])
        assert result.total_files == 0
        assert len(result.languages) == 0

    def test_single_file(self):
        docs = [_make_doc("x = 1\ny = 2\n", language="python")]
        result = analyze_languages(docs)
        assert result.total_files == 1
        assert result.total_lines == 2
        assert "python" in result.languages
        assert result.languages["python"].file_count == 1

    def test_multiple_languages(self):
        docs = [
            _make_doc("x = 1", language="python"),
            _make_doc("const x = 1;", language="javascript"),
            _make_doc("<h1>Hi</h1>", language="html"),
        ]
        result = analyze_languages(docs)
        assert result.total_files == 3
        assert len(result.languages) == 3

    def test_language_detection_from_content(self):
        docs = [_make_doc("console.log('hi');", file_path="/repo/a.js", relative_path="a.js")]
        result = analyze_languages(docs)
        assert "javascript" in result.languages

    def test_per_file_listing(self):
        docs = [
            _make_doc("x = 1\n" * 10, language="python"),
            _make_doc("y = 2\n" * 20, language="python"),
        ]
        result = analyze_languages(docs)
        assert len(result.languages["python"].files) == 2

    def test_size_tracking(self):
        content = "hello world\n" * 100
        docs = [_make_doc(content, language="text")]
        result = analyze_languages(docs)
        assert result.total_bytes > 0
        assert result.languages["text"].total_bytes > 0

    def test_metadata_language_preferred(self):
        """If metadata already has a language, use it instead of re-detecting."""
        docs = [_make_doc("hello", language="markdown")]
        result = analyze_languages(docs)
        assert "markdown" in result.languages

    def test_no_metadata_path_skipped(self):
        docs = [{"content": "hello", "metadata": {}}]
        result = analyze_languages(docs)
        assert result.total_files == 0


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

class TestDistributionBar:
    def test_full(self):
        lb = LanguageBreakdown("python", total_lines=100)
        bar = distribution_bar(lb, 100, width=10)
        assert bar == "#" * 10

    def test_half(self):
        lb = LanguageBreakdown("python", total_lines=50)
        bar = distribution_bar(lb, 100, width=10)
        assert bar.count("#") == 5

    def test_empty(self):
        lb = LanguageBreakdown("python", total_lines=0)
        bar = distribution_bar(lb, 100, width=10)
        assert bar == "." * 10

    def test_zero_total(self):
        lb = LanguageBreakdown("python", total_lines=10)
        bar = distribution_bar(lb, 0, width=10)
        assert bar == ""


class TestFormatPercentage:
    def test_basic(self):
        assert format_percentage(1, 2) == "50.0%"

    def test_zero_total(self):
        assert format_percentage(0, 0) == "0.0%"

    def test_small(self):
        assert format_percentage(1, 1000) == "0.1%"


class TestFormatByteSize:
    def test_bytes(self):
        assert format_byte_size(500) == "500 B"

    def test_kb(self):
        assert format_byte_size(1536) == "1.5 KB"

    def test_mb(self):
        assert format_byte_size(2 * 1024 * 1024) == "2.0 MB"
