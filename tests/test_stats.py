"""Tests for repo2readme.services.stats — the project health analysis engine."""

from __future__ import annotations

import pytest

from repo2readme.services.stats import (
    FileStats,
    LanguageStats,
    RepoStats,
    _count_comment_lines,
    _estimate_complexity,
    _has_docstring,
    _is_config_file,
    _is_doc_file,
    _is_test_file,
    _size_bucket,
    _top_level_dir,
    analyze_repository,
    format_bytes,
    format_stats_summary,
    health_bar,
)


def _make_doc(content: str = "", file_path: str = "/repo/src/main.py",
              relative_path: str = "src/main.py") -> dict:
    return {"content": content, "metadata": {"file_path": file_path, "relative_path": relative_path}}


def _py_doc(code: str = "def foo(): pass", name: str = "main.py") -> dict:
    return _make_doc(code, f"/repo/src/{name}", f"src/{name}")


# ---------------------------------------------------------------------------
# Comment detection
# ---------------------------------------------------------------------------

class TestCountCommentLines:
    def test_python(self):
        assert _count_comment_lines("# a\nx = 1\n# b", "python") == 2

    def test_no_comments(self):
        assert _count_comment_lines("x = 1\ny = 2", "python") == 0

    def test_javascript(self):
        content = "// line\nconst x = 1;\n/* block\n * comment\n */"
        assert _count_comment_lines(content, "javascript") == 4

    def test_unknown_and_empty(self):
        assert _count_comment_lines("# hello", "unknown") == 0
        assert _count_comment_lines("", "python") == 0

    def test_rust(self):
        content = "// line\n/* block */\n * cont\nlet x = 1;"
        assert _count_comment_lines(content, "rust") == 3


# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------

class TestEstimateComplexity:
    def test_simple(self):
        assert _estimate_complexity("def foo():\n    return 1", "python") == 1

    def test_if_else(self):
        assert _estimate_complexity("if x:\n    a()\nelse:\n    b()", "python") == 2

    def test_for_if(self):
        assert _estimate_complexity("for i in range(10):\n    if i > 5:\n        pass", "python") == 3

    def test_unknown_baseline(self):
        assert _estimate_complexity("", "unknown") == 1

    def test_javascript(self):
        code = "if (x) {\n  for (var i=0; i<10; i++) {\n    while (true) {}\n  }\n}"
        assert _estimate_complexity(code, "javascript") >= 4

    def test_nested_python(self):
        code = "if a:\n    if b:\n        for c in d:\n            while e:\n                pass"
        assert _estimate_complexity(code, "python") >= 4


# ---------------------------------------------------------------------------
# Docstring detection
# ---------------------------------------------------------------------------

class TestHasDocstring:
    def test_python_triple_double(self):
        assert _has_docstring('"""\nModule doc\n"""\nx = 1', "python") is True

    def test_python_triple_single(self):
        assert _has_docstring("'''\nModule doc\n'''\nx = 1", "python") is True

    def test_no_docstring(self):
        assert _has_docstring("x = 1", "python") is False

    def test_javadoc(self):
        assert _has_docstring("/**\n * Doc\n */", "javascript") is True

    def test_empty(self):
        assert _has_docstring("", "python") is False


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestIsDocFile:
    def test_readme(self):
        assert _is_doc_file("README.md") is True
        assert _is_doc_file("CHANGELOG") is True
        assert _is_doc_file("LICENSE.txt") is True
        assert _is_doc_file("docs/guides/intro.rst") is True

    def test_non_doc(self):
        assert _is_doc_file("src/main.py") is False


class TestIsTestFile:
    def test_positive(self):
        assert _is_test_file("tests/test_main.py") is True
        assert _is_test_file("src/utils.spec.ts") is True
        assert _is_test_file("spec/models/user_spec.rb") is True

    def test_negative(self):
        assert _is_test_file("src/main.py") is False


class TestIsConfigFile:
    def test_package_json(self):
        assert _is_config_file("package.json") is True

    def test_pyproject(self):
        assert _is_config_file("pyproject.toml") is True

    def test_makefile(self):
        assert _is_config_file("Makefile") is True

    def test_source_file(self):
        assert _is_config_file("src/main.py") is False


# ---------------------------------------------------------------------------
# Size / path helpers
# ---------------------------------------------------------------------------

class TestSizeBucket:
    def test_small(self):
        assert _size_bucket(500) == "< 1 KB"

    def test_ranges(self):
        assert _size_bucket(5 * 1024) == "1-10 KB"
        assert _size_bucket(75 * 1024) == "50-100 KB"
        assert _size_bucket(200 * 1024) == "> 100 KB"


class TestTopLevelDir:
    def test_nested(self):
        assert _top_level_dir("src/utils/helpers.py") == "src"

    def test_root_file(self):
        assert _top_level_dir("README.md") == "."


class TestFormatBytes:
    def test_all(self):
        assert format_bytes(500) == "500 B"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(2 * 1024 * 1024) == "2.0 MB"


class TestHealthBar:
    def test_scores(self):
        assert "90/100" in health_bar(90)
        assert "0/100" in health_bar(0)


class TestFormatStatsSummary:
    def test_single(self):
        stats = RepoStats(total_files=5, total_code_lines=100,
                          languages={"python": LanguageStats(name="python", code_lines=100)})
        assert "1 language" in format_stats_summary(stats)

    def test_multi(self):
        stats = RepoStats(total_files=10, total_code_lines=200, languages={
            "python": LanguageStats(name="python", code_lines=100),
            "js": LanguageStats(name="js", code_lines=100),
        })
        assert "2 languages" in format_stats_summary(stats)


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

class TestAnalyzeRepository:
    def test_empty(self):
        stats = analyze_repository([], "/repo")
        assert stats.total_files == 0 and len(stats.languages) == 0

    def test_single_python(self):
        content = '"""Doc."""\nimport os\n\ndef main():\n    print("hi")\n'
        stats = analyze_repository([_make_doc(content, "/repo/app.py", "app.py")], "/repo")
        assert stats.total_files == 1 and "python" in stats.languages

    def test_multi_lang(self):
        docs = [
            _make_doc("console.log('hi');", "/repo/index.js", "index.js"),
            _make_doc("x = 1", "/repo/app.py", "app.py"),
            _make_doc("<html></html>", "/repo/index.html", "index.html"),
        ]
        stats = analyze_repository(docs, "/repo")
        assert stats.total_files == 3 and len(stats.languages) >= 2

    def test_largest_files(self):
        small = _make_doc("x = 1", "/repo/a.py", "a.py")
        big = _make_doc("x = 1\n" * 500, "/repo/b.py", "b.py")
        stats = analyze_repository([small, big], "/repo")
        assert stats.largest_files[0].relative_path == "b.py"

    def test_complexity_ranking(self):
        simple = _make_doc("x = 1", "/repo/s.py", "s.py")
        cx = _make_doc("if a:\n  if b:\n    for c in d:\n      while e:\n        if f:\n          pass", "/repo/c.py", "c.py")
        stats = analyze_repository([simple, cx], "/repo")
        assert stats.most_complex_files[0].relative_path == "c.py"

    def test_classifications(self):
        docs = [
            _make_doc("# Intro", "/repo/docs/intro.md", "docs/intro.md"),
            _make_doc("# Setup", "/repo/docs/setup.md", "docs/setup.md"),
            _make_doc("def test_ok(): pass", "/repo/tests/t.py", "tests/t.py"),
            _make_doc("x = 1", "/repo/src/main.py", "src/main.py"),
            _make_doc("y = 2", "/repo/src/b.py", "src/b.py"),
        ]
        stats = analyze_repository(docs, "/repo")
        assert stats.documentation_files == 2
        assert stats.test_files == 1
        assert "src" in stats.top_level_dirs
        assert stats.top_level_dirs["src"].file_count == 2

    def test_health_scores_in_range(self):
        docs = [
            _py_doc('"""Doc."""\ndef foo(): pass', "main.py"),
            _py_doc("def test_foo(): pass", "test_main.py"),
            _make_doc("# README\nReadme", "README.md", "README.md"),
        ]
        stats = analyze_repository(docs, "/repo")
        assert 0 <= stats.documentation_score <= 100
        assert 0 <= stats.code_quality_score <= 100
        assert 0 <= stats.project_maturity_score <= 100

    def test_blank_and_comment_separation(self):
        content = "# comment\n\nx = 1\n# another\n\ny = 2\n"
        stats = analyze_repository([_make_doc(content, "/repo/m.py", "m.py")], "/repo")
        assert stats.total_blank_lines == 2 and stats.total_comment_lines == 2

    def test_no_metadata_skips(self):
        stats = analyze_repository([{"content": "hello", "metadata": {}}], "/repo")
        assert stats.total_files == 0

    def test_large_project(self):
        docs = [_py_doc(f"# line {i}\nx{i} = {i}", f"mod{i}.py") for i in range(60)]
        stats = analyze_repository(docs, "/repo")
        assert stats.total_files == 60
        assert stats.project_maturity_score > 0
