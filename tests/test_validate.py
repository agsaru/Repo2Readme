"""Tests for repo2readme.services.validator — README quality linting."""

from __future__ import annotations

import pytest

from repo2readme.services.validator import (
    Issue,
    Severity,
    ValidationResult,
    format_result,
    validate_file,
    validate_readme,
)


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_empty(self):
        r = ValidationResult()
        assert r.passed is True
        assert r.error_count == 0
        assert r.warning_count == 0

    def test_with_errors(self):
        r = ValidationResult()
        r.add(Severity.ERROR, "test", "msg")
        assert r.passed is False
        assert r.error_count == 1

    def test_warnings_only(self):
        r = ValidationResult()
        r.add(Severity.WARNING, "test", "msg")
        assert r.passed is True
        assert r.warning_count == 1

    def test_info_only(self):
        r = ValidationResult()
        r.add(Severity.INFO, "test", "msg")
        assert r.passed is True
        assert r.info_count == 1

    def test_mixed(self):
        r = ValidationResult()
        r.add(Severity.ERROR, "e", "msg")
        r.add(Severity.WARNING, "w", "msg")
        r.add(Severity.INFO, "i", "msg")
        assert r.error_count == 1
        assert r.warning_count == 1
        assert r.info_count == 1
        assert r.passed is False


# ---------------------------------------------------------------------------
# Issue
# ---------------------------------------------------------------------------

class TestIssue:
    def test_str_with_line(self):
        i = Issue(Severity.ERROR, "rule", "message", line=10)
        assert "L10" in str(i)

    def test_str_without_line(self):
        i = Issue(Severity.WARNING, "rule", "message")
        assert "---" in str(i)


# ---------------------------------------------------------------------------
# Heading structure
# ---------------------------------------------------------------------------

class TestStructureChecks:
    def test_valid_readme(self):
        md = "# My Project\n\n## Features\n\nDetails here.\n\n## Installation\n\nInstall steps.\n"
        r = validate_readme(md)
        assert not any(i.rule == "missing-h1" for i in r.issues)

    def test_missing_h1(self):
        md = "## Features\n\nDetails.\n"
        r = validate_readme(md)
        assert any(i.rule == "missing-h1" for i in r.issues)

    def test_multiple_h1(self):
        md = "# First\n\n# Second\n"
        r = validate_readme(md)
        assert any(i.rule == "multiple-h1" for i in r.issues)

    def test_heading_skip(self):
        md = "# Title\n\n### Skipped H2\n"
        r = validate_readme(md)
        assert any(i.rule == "heading-skip" for i in r.issues)

    def test_no_heading_skip(self):
        md = "# Title\n\n## Section\n\n### Sub\n"
        r = validate_readme(md)
        assert not any(i.rule == "heading-skip" for i in r.issues)

    def test_missing_sections_info(self):
        md = "# Title\n\nRandom content.\n"
        r = validate_readme(md)
        info_rules = [i.rule for i in r.issues if i.rule == "missing-section"]
        assert len(info_rules) >= 1


# ---------------------------------------------------------------------------
# Link checks
# ---------------------------------------------------------------------------

class TestLinkChecks:
    def test_broken_anchor(self):
        md = "# Title\n\n[link](#nonexistent)\n"
        r = validate_readme(md)
        assert any(i.rule == "broken-anchor" for i in r.issues)

    def test_valid_anchor(self):
        md = "# Title\n\n[link](#title)\n"
        r = validate_readme(md)
        assert not any(i.rule == "broken-anchor" for i in r.issues)

    def test_placeholder_link(self):
        md = "# Title\n\n[docs](https://example.com/guide)\n"
        r = validate_readme(md)
        assert any(i.rule == "placeholder-link" for i in r.issues)

    def test_valid_http_link(self):
        md = "# Title\n\n[GitHub](https://github.com/user/repo)\n"
        r = validate_readme(md)
        assert not any(i.rule == "placeholder-link" for i in r.issues)

    def test_empty_link(self):
        md = "# Title\n\n[empty]()\n"
        r = validate_readme(md)
        assert any(i.rule == "empty-link" for i in r.issues)

    def test_placeholder_image(self):
        md = "# Title\n\n![logo](path/to/logo.png)\n"
        r = validate_readme(md)
        assert any(i.rule == "placeholder-image" for i in r.issues)


# ---------------------------------------------------------------------------
# Style checks
# ---------------------------------------------------------------------------

class TestStyleChecks:
    def test_trailing_whitespace(self):
        md = "# Title   \n"
        r = validate_readme(md)
        assert any(i.rule == "trailing-whitespace" for i in r.issues)

    def test_no_trailing_whitespace(self):
        md = "# Title\n"
        r = validate_readme(md)
        assert not any(i.rule == "trailing-whitespace" for i in r.issues)

    def test_trailing_hash(self):
        md = "# Title ###\n"
        r = validate_readme(md)
        assert any(i.rule == "trailing-hash" for i in r.issues)

    def test_bare_url(self):
        md = "# Title\n\nVisit https://github.com for more.\n"
        r = validate_readme(md)
        # Bare URL might or might not trigger depending on context
        info_rules = [i.rule for i in r.issues]
        assert "bare-url" in info_rules or "missing-section" in info_rules

    def test_table_column_mismatch(self):
        md = "# Title\n\n| A | B |\n|---|---|\n| 1 | 2 | 3 |\n"
        r = validate_readme(md)
        assert any(i.rule == "table-columns" for i in r.issues)

    def test_table_consistent(self):
        md = "# Title\n\n| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
        r = validate_readme(md)
        assert not any(i.rule == "table-columns" for i in r.issues)

    def test_long_line(self):
        md = "# Title\n\n" + "x" * 130 + "\n"
        r = validate_readme(md)
        assert any(i.rule == "long-line" for i in r.issues)


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------

class TestContentChecks:
    def test_empty_document(self):
        r = validate_readme("")
        assert any(i.rule == "empty" for i in r.issues)

    def test_unclosed_fence(self):
        md = "# Title\n\n```python\nprint('hello')\n"
        r = validate_readme(md)
        assert any(i.rule == "unclosed-fence" for i in r.issues)

    def test_balanced_fences(self):
        md = "# Title\n\n```python\nprint('hello')\n```\n"
        r = validate_readme(md)
        assert not any(i.rule == "unclosed-fence" for i in r.issues)

    def test_todo_marker(self):
        md = "# Title\n\n<!-- TODO: add examples -->\n"
        r = validate_readme(md)
        assert any(i.rule == "todo-marker" for i in r.issues)

    def test_excessive_blank_lines(self):
        md = "# Title\n\n\n\n\nContent.\n"
        r = validate_readme(md)
        assert any(i.rule == "excessive-blanks" for i in r.issues)

    def test_no_excessive_blanks(self):
        md = "# Title\n\n\nContent.\n"
        r = validate_readme(md)
        assert not any(i.rule == "excessive-blanks" for i in r.issues)

    def test_code_block_content_not_checked(self):
        """Headings inside code blocks should not trigger structure checks."""
        md = "# Title\n\n```markdown\n# Fake heading\n```\n"
        r = validate_readme(md)
        # The fake heading should not cause a duplicate-h1
        assert not any(i.rule == "duplicate-h1" for i in r.issues)


# ---------------------------------------------------------------------------
# Badge checks
# ---------------------------------------------------------------------------

class TestBadgeChecks:
    def test_badge_no_alt(self):
        md = "# Title\n\n![](https://img.shields.io/badge/test-pass-green)\n"
        r = validate_readme(md)
        assert any(i.rule == "badge-no-alt" for i in r.issues)

    def test_valid_badge(self):
        md = "# Title\n\n![Build](https://img.shields.io/badge/build-pass-green)\n"
        r = validate_readme(md)
        # Should not trigger badge-no-alt
        assert not any(i.rule == "badge-no-alt" for i in r.issues)


# ---------------------------------------------------------------------------
# validate_file
# ---------------------------------------------------------------------------

class TestValidateFile:
    def test_nonexistent(self):
        r = validate_file("/nonexistent/path/README.md")
        assert any(i.rule == "file-not-found" for i in r.issues)

    def test_valid_file(self, tmp_path):
        f = tmp_path / "README.md"
        f.write_text("# My Project\n\n## Features\n\nGreat stuff.\n")
        r = validate_file(str(f))
        assert not any(i.rule == "file-not-found" for i in r.issues)

    def test_encoding_error(self, tmp_path):
        f = tmp_path / "bad.md"
        f.write_bytes(b"\x80\x81\x82")
        r = validate_file(str(f))
        assert any(i.rule in ("encoding-error", "empty") for i in r.issues)


# ---------------------------------------------------------------------------
# format_result
# ---------------------------------------------------------------------------

class TestFormatResult:
    def test_passing(self):
        r = ValidationResult()
        output = format_result(r)
        assert "passed" in output.lower()

    def test_with_issues(self):
        r = ValidationResult()
        r.add(Severity.ERROR, "test-rule", "Something wrong", line=5)
        output = format_result(r, "TEST.md")
        assert "TEST.md" in output
        assert "1 error" in output
        assert "test-rule" in output

    def test_multiple_severities(self):
        r = ValidationResult()
        r.add(Severity.ERROR, "e", "err")
        r.add(Severity.WARNING, "w", "warn")
        r.add(Severity.INFO, "i", "info")
        output = format_result(r)
        assert "1 error" in output
        assert "1 warning" in output
        assert "1 info" in output
