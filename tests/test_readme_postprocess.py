import logging

import pytest

from repo2readme.readme.postprocess import (
    ValidationIssue,
    extract_headings,
    extract_internal_links,
    find_broken_anchor_links,
    find_heading_problems,
    find_placeholder_images,
    github_anchor,
    iter_prose_lines,
    normalize_markdown,
    postprocess_readme,
    strip_wrapping_code_fence,
    validate_markdown,
)


class TestAnchors:
    def test_lowercases_and_hyphenates(self):
        assert github_anchor("Getting Started") == "getting-started"

    def test_drops_punctuation(self):
        assert github_anchor("What's new?") == "whats-new"

    def test_drops_emoji(self):
        assert github_anchor("Features 🚀") == "features"

    def test_keeps_existing_hyphens_and_digits(self):
        assert github_anchor("Python 3.10 set-up") == "python-310-set-up"

    def test_uses_only_the_label_of_a_linked_heading(self):
        assert github_anchor("[Usage](docs/usage.md)") == "usage"

    def test_strips_inline_code_markers(self):
        assert github_anchor("The `run` command") == "the-run-command"


class TestFenceAwareScanning:
    def test_lines_inside_code_blocks_are_skipped(self):
        text = "# Real\n\n```md\n# Not a heading\n```\n\n## Also real\n"
        assert [line for _, line in iter_prose_lines(text)] == [
            "# Real",
            "",
            "",
            "## Also real",
        ]

    def test_tilde_fences_are_handled(self):
        text = "# Real\n~~~\n# hidden\n~~~\n"
        assert [line for _, line in iter_prose_lines(text)] == ["# Real"]

    def test_headings_inside_code_blocks_are_ignored(self):
        text = "# Project\n\n```markdown\n# Example Title\n## Example Section\n```\n"
        assert [heading for _, heading, _ in extract_headings(text)] == ["Project"]

    def test_links_inside_code_blocks_are_ignored(self):
        text = "# P\n\n```\n[TOC](#nope)\n```\n"
        assert extract_internal_links(text) == []


class TestHeadingExtraction:
    def test_levels_and_anchors(self):
        text = "# Title\n\n## Key Features\n\n### Sub Section\n"
        assert extract_headings(text) == [
            (1, "Title", "title"),
            (2, "Key Features", "key-features"),
            (3, "Sub Section", "sub-section"),
        ]

    def test_closing_hashes_are_stripped(self):
        assert extract_headings("## Usage ##\n") == [(2, "Usage", "usage")]

    def test_duplicate_headings_get_suffixed_anchors(self):
        text = "# T\n\n## Usage\n\n## Usage\n"
        assert [anchor for _, _, anchor in extract_headings(text)] == [
            "t",
            "usage",
            "usage-1",
        ]

    def test_hash_without_a_space_is_not_a_heading(self):
        assert extract_headings("#NotAHeading\n") == []


class TestStripWrappingFence:
    def test_unwraps_a_fully_fenced_document(self):
        text = "```markdown\n# Title\n\nSome text.\n```"
        assert strip_wrapping_code_fence(text) == "# Title\n\nSome text."

    def test_unwraps_a_bare_fence(self):
        assert strip_wrapping_code_fence("```\n# Title\n```") == "# Title"

    def test_tolerates_blank_lines_around_the_fence(self):
        text = "\n\n```markdown\n# Title\n```\n\n"
        assert strip_wrapping_code_fence(text) == "# Title"

    def test_leaves_a_document_that_merely_contains_code(self):
        text = "# Title\n\n```bash\npip install x\n```\n"
        assert strip_wrapping_code_fence(text) == text

    def test_leaves_a_document_starting_with_a_code_block(self):
        text = "```bash\npip install x\n```\n\n# Title\n"
        assert strip_wrapping_code_fence(text) == text

    def test_does_not_unwrap_when_the_closing_fence_is_tagged(self):
        text = "```python\nx = 1\n```python\n"
        assert strip_wrapping_code_fence(text) == text

    def test_keeps_inner_code_blocks_intact(self):
        text = "```markdown\n# Title\n\n```bash\nls\n```\n\nDone.\n```"
        result = strip_wrapping_code_fence(text)
        assert result.startswith("# Title")
        assert "```bash" in result

    def test_empty_input(self):
        assert strip_wrapping_code_fence("") == ""


class TestNormalize:
    def test_trailing_whitespace_is_removed(self):
        assert normalize_markdown("# Title   \n\ntext  \n") == "# Title\n\ntext\n"

    def test_blank_line_runs_are_collapsed(self):
        assert normalize_markdown("# A\n\n\n\n\n## B\n") == "# A\n\n\n## B\n"

    def test_leading_and_trailing_blank_lines_are_dropped(self):
        assert normalize_markdown("\n\n# A\n\n\n") == "# A\n"

    def test_exactly_one_trailing_newline(self):
        assert normalize_markdown("# A").endswith("A\n")
        assert not normalize_markdown("# A\n\n\n").endswith("\n\n")

    def test_windows_line_endings_are_normalized(self):
        assert normalize_markdown("# A\r\n\r\ntext\r\n") == "# A\n\ntext\n"

    def test_wrapping_fence_is_removed(self):
        assert normalize_markdown("```markdown\n# A\n```") == "# A\n"

    @pytest.mark.parametrize("text", ["", "   ", "\n\n"])
    def test_blank_input_returns_empty(self, text):
        assert normalize_markdown(text) == ""


class TestAnchorValidation:
    def test_matching_toc_passes(self):
        text = "# Title\n\n- [Key Features](#key-features)\n\n## Key Features\n"
        assert find_broken_anchor_links(text) == []

    def test_stale_anchor_is_reported(self):
        text = "# Title\n\n- [Key Features](#key-features)\n\n## Features\n"
        issues = find_broken_anchor_links(text)

        assert len(issues) == 1
        assert issues[0].kind == "broken-anchor"
        assert "#key-features" in issues[0].message

    def test_external_links_are_ignored(self):
        text = "# Title\n\n[docs](https://example.org/docs)\n"
        assert find_broken_anchor_links(text) == []

    def test_relative_file_links_are_ignored(self):
        text = "# Title\n\n[usage](./docs/usage.md)\n"
        assert find_broken_anchor_links(text) == []

    def test_duplicate_heading_anchors_resolve(self):
        text = "# T\n\n[second](#usage-1)\n\n## Usage\n\n## Usage\n"
        assert find_broken_anchor_links(text) == []

    def test_emoji_in_toc_label_does_not_break_matching(self):
        text = "# T\n\n- [🚀 Features](#features)\n\n## Features\n"
        assert find_broken_anchor_links(text) == []


class TestImageValidation:
    def test_empty_markdown_image_target(self):
        issues = find_placeholder_images("# T\n\n![badge]()\n")
        assert [issue.kind for issue in issues] == ["placeholder-image"]

    def test_placeholder_path(self):
        issues = find_placeholder_images("# T\n\n![logo](path/to/logo.png)\n")
        assert len(issues) == 1

    def test_empty_html_image_src(self):
        issues = find_placeholder_images('# T\n\n<img src="" alt="logo">\n')
        assert len(issues) == 1

    def test_html_image_without_src(self):
        issues = find_placeholder_images("# T\n\n<img alt='logo'>\n")
        assert len(issues) == 1

    def test_real_https_image_is_accepted(self):
        text = "# T\n\n![build](https://img.shields.io/badge/build-passing-green)\n"
        assert find_placeholder_images(text) == []

    def test_relative_repo_image_is_accepted(self):
        assert find_placeholder_images("# T\n\n![logo](assets/logo.png)\n") == []

    def test_placeholder_inside_a_code_block_is_ignored(self):
        text = "# T\n\n```markdown\n![logo](path/to/logo.png)\n```\n"
        assert find_placeholder_images(text) == []


class TestHeadingProblems:
    def test_single_h1_passes(self):
        assert find_heading_problems("# Title\n\n## Section\n") == []

    def test_missing_h1_is_reported(self):
        issues = find_heading_problems("## Section\n")
        assert [issue.kind for issue in issues] == ["missing-h1"]

    def test_duplicate_h1_is_reported(self):
        issues = find_heading_problems("# One\n\n# Two\n")
        assert issues[0].kind == "duplicate-h1"
        assert "One" in issues[0].message and "Two" in issues[0].message


class TestValidate:
    def test_a_clean_readme_has_no_issues(self):
        text = (
            "# Project\n\n"
            "## Table of Contents\n\n"
            "- [Installation](#installation)\n"
            "- [Usage](#usage)\n\n"
            "## Installation\n\n"
            "```bash\npip install project\n```\n\n"
            "## Usage\n\n"
            "Run it.\n"
        )
        assert validate_markdown(text) == []

    def test_empty_document_is_reported(self):
        issues = validate_markdown("   \n")
        assert [issue.kind for issue in issues] == ["empty"]

    def test_issues_are_reported_together(self):
        text = "## Section\n\n[missing](#nope)\n\n![logo](path/to/logo.png)\n"
        kinds = {issue.kind for issue in validate_markdown(text)}
        assert kinds == {"missing-h1", "broken-anchor", "placeholder-image"}

    def test_issue_renders_readably(self):
        issue = ValidationIssue(kind="broken-anchor", message="link '#x'")
        assert str(issue) == "broken-anchor: link '#x'"


class TestPostprocess:
    def test_normalizes_and_validates_together(self):
        readme, issues = postprocess_readme("```markdown\n# Title   \n\n\n\n\n```")

        assert readme == "# Title\n"
        assert issues == []

    def test_validation_runs_on_the_normalized_text(self):
        # The fence would hide the heading from the validator if it ran first.
        readme, issues = postprocess_readme("```markdown\n## Only H2\n```")

        assert readme == "## Only H2\n"
        assert [issue.kind for issue in issues] == ["missing-h1"]


class TestOrchestratorIntegration:
    def _patch_workflow(self, monkeypatch, readme_text):
        from repo2readme.services import orchestrator

        class FakeWorkflow:
            def invoke(self, _state):
                return {"best_readme": readme_text}

        monkeypatch.setattr(orchestrator, "build_workflow", lambda: FakeWorkflow())
        return orchestrator

    def test_pipeline_returns_normalized_markdown(self, monkeypatch):
        orchestrator = self._patch_workflow(
            monkeypatch, "```markdown\n# Title\n\nBody.   \n```"
        )

        result = orchestrator.run_pipeline(
            summaries=[], tree="", dependency_overview="",
        )

        assert result == "# Title\n\nBody.\n"

    def test_pipeline_logs_validation_warnings(self, monkeypatch, caplog):
        orchestrator = self._patch_workflow(
            monkeypatch, "# Title\n\n- [Features](#features)\n\n## Capabilities\n"
        )

        with caplog.at_level(logging.WARNING, logger="repo2readme.services.orchestrator"):
            orchestrator.run_pipeline(
                summaries=[], tree="", dependency_overview="",
            )

        assert "broken-anchor" in caplog.text
        assert "#features" in caplog.text

    def test_pipeline_stays_quiet_for_a_clean_readme(self, monkeypatch, caplog):
        orchestrator = self._patch_workflow(monkeypatch, "# Title\n\nBody.\n")

        with caplog.at_level(logging.WARNING, logger="repo2readme.services.orchestrator"):
            orchestrator.run_pipeline(
                summaries=[], tree="", dependency_overview="",
            )

        assert caplog.text == ""
