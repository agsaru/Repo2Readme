import importlib

from click.testing import CliRunner

from repo2readme.services.reporting import (
    MAX_REASON_LENGTH,
    FailureGroup,
    SummaryFailure,
    as_failure,
    build_report_lines,
    group_failures,
    is_failed_summary,
    partition_summaries,
    render_report,
    truncate_reason,
)

cli_main = importlib.import_module("repo2readme.cli.main")


class TestFailureDetection:
    def test_error_dict_is_a_failure(self):
        assert is_failed_summary({"file_path": "a.py", "error": "boom"})

    def test_normal_summary_is_not_a_failure(self):
        assert not is_failed_summary({"file_path": "a.py", "description": "does x"})

    def test_summary_describing_errors_is_not_a_failure(self):
        # A summary of an error-handling module has no top-level "error" key.
        summary = {
            "file_path": "errors.py",
            "description": "Defines error classes",
            "classes": [{"name": "ApiError", "description": "raised on failure"}],
        }
        assert not is_failed_summary(summary)

    def test_empty_or_null_error_is_not_a_failure(self):
        assert not is_failed_summary({"file_path": "a.py", "error": ""})
        assert not is_failed_summary({"file_path": "a.py", "error": "   "})
        assert not is_failed_summary({"file_path": "a.py", "error": None})

    def test_non_dict_entries_are_not_failures(self):
        assert not is_failed_summary("just a string")
        assert not is_failed_summary(None)
        assert not is_failed_summary(["a", "b"])

    def test_as_failure_handles_missing_path(self):
        failure = as_failure({"error": "boom"})
        assert failure.file_path == "<unknown file>"
        assert failure.reason == "boom"


class TestPartition:
    def test_splits_successes_from_failures(self):
        summaries = [
            {"file_path": "a.py", "description": "a"},
            {"file_path": "b.py", "error": "429 rate limit"},
            {"file_path": "c.py", "description": "c"},
        ]

        successful, failures = partition_summaries(summaries)

        assert [s["file_path"] for s in successful] == ["a.py", "c.py"]
        assert failures == [SummaryFailure(file_path="b.py", reason="429 rate limit")]

    def test_strings_are_kept_as_successes(self):
        successful, failures = partition_summaries(["plain summary"])
        assert successful == ["plain summary"]
        assert failures == []

    def test_empty_input(self):
        assert partition_summaries([]) == ([], [])

    def test_input_is_not_mutated(self):
        summaries = [{"file_path": "a.py", "error": "boom"}]
        partition_summaries(summaries)
        assert summaries == [{"file_path": "a.py", "error": "boom"}]


class TestReasonFormatting:
    def test_whitespace_is_collapsed(self):
        assert truncate_reason("rate\n  limit\treached") == "rate limit reached"

    def test_long_reason_is_truncated_with_ellipsis(self):
        reason = "x" * (MAX_REASON_LENGTH + 50)
        result = truncate_reason(reason)
        assert len(result) == MAX_REASON_LENGTH
        assert result.endswith("...")

    def test_short_reason_is_untouched(self):
        assert truncate_reason("timeout") == "timeout"

    def test_blank_reason_gets_a_placeholder(self):
        assert truncate_reason("   ") == "unknown error"

    def test_non_string_reason_is_accepted(self):
        assert truncate_reason(429) == "429"


class TestGrouping:
    def test_identical_reasons_collapse_into_one_group(self):
        failures = [SummaryFailure(f"f{i}.py", "429 rate limit") for i in range(30)]

        groups = group_failures(failures)

        assert len(groups) == 1
        assert isinstance(groups[0], FailureGroup)
        assert groups[0].count == 30
        assert groups[0].reason == "429 rate limit"

    def test_groups_are_ordered_by_frequency(self):
        failures = [
            SummaryFailure("a.py", "timeout"),
            SummaryFailure("b.py", "429 rate limit"),
            SummaryFailure("c.py", "429 rate limit"),
        ]

        groups = group_failures(failures)

        assert [g.reason for g in groups] == ["429 rate limit", "timeout"]

    def test_equal_counts_are_ordered_deterministically(self):
        failures = [
            SummaryFailure("a.py", "zebra"),
            SummaryFailure("b.py", "alpha"),
        ]
        assert [g.reason for g in group_failures(failures)] == ["alpha", "zebra"]

    def test_reasons_differing_only_in_whitespace_group_together(self):
        failures = [
            SummaryFailure("a.py", "429  rate\nlimit"),
            SummaryFailure("b.py", "429 rate limit"),
        ]
        assert len(group_failures(failures)) == 1


class TestReportLines:
    def test_no_failures_produces_no_output(self):
        assert build_report_lines(total=3, succeeded=3, failures=[]) == []

    def test_counts_are_reported(self):
        failures = [SummaryFailure("b.py", "boom")]
        text = "\n".join(build_report_lines(total=3, succeeded=2, failures=failures))

        assert "Succeeded          : 2/3" in text
        assert "Failed             : 1/3" in text
        assert "b.py" in text
        assert "boom" in text

    def test_long_group_is_capped_with_a_more_line(self):
        failures = [SummaryFailure(f"f{i}.py", "boom") for i in range(9)]
        text = "\n".join(
            build_report_lines(total=9, succeeded=0, failures=failures, max_paths_per_group=5)
        )

        assert "f0.py" in text
        assert "f8.py" not in text
        assert "... and 4 more" in text

    def test_render_report_uses_the_printer(self):
        printed = []
        render_report(2, 1, [SummaryFailure("b.py", "boom")], printed.append)
        assert any("b.py" in line for line in printed)

    def test_render_report_stays_silent_on_success(self):
        printed = []
        render_report(2, 2, [], printed.append)
        assert printed == []


def _patch_pipeline(monkeypatch, summaries, errors=None, readme="# Generated"):
    """Patch the CLI so a run completes without touching any provider."""
    captured = {}

    def fake_setup_api_keys(*settings):
        return None

    def fake_generate_all_summaries(documents, summary_cache, provider, model,
                                    base_url, progress, task_id, **kwargs):
        return summaries, list(errors or [])

    def fake_generate_hierarchical_summaries(file_summaries, provider, model,
                                             base_url, progress, task_id):
        captured["rollup_input"] = file_summaries
        return file_summaries

    def fake_run_pipeline(summaries, tree, dependency_overview, settings=None, reviewer_settings=None):
        captured["readme_input"] = summaries
        return readme

    monkeypatch.setattr(cli_main, "setup_api_keys", fake_setup_api_keys)
    monkeypatch.setattr(cli_main, "generate_all_summaries", fake_generate_all_summaries)
    monkeypatch.setattr(
        cli_main, "generate_hierarchical_summaries", fake_generate_hierarchical_summaries
    )
    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)
    return captured


def _repo(tmp_path, count=2):
    for i in range(count):
        (tmp_path / f"file{i}.py").write_text(f"x = {i}", encoding="utf-8")
    return str(tmp_path)


class TestCliReporting:
    def test_failures_are_reported_to_the_user(self, monkeypatch, tmp_path):
        _patch_pipeline(
            monkeypatch,
            summaries=[
                {"file_path": "file0.py", "description": "ok"},
                {"file_path": "file1.py", "error": "Error code: 429 rate limit"},
            ],
        )

        result = CliRunner().invoke(
            cli_main.main, ["run", "--local", _repo(tmp_path), "--force"]
        )

        assert result.exit_code == 0
        assert "Summarization report" in result.output
        assert "429" in result.output
        assert "file1.py" in result.output

    def test_failed_summaries_never_reach_the_readme_prompt(self, monkeypatch, tmp_path):
        captured = _patch_pipeline(
            monkeypatch,
            summaries=[
                {"file_path": "file0.py", "description": "ok"},
                {"file_path": "file1.py", "error": "boom"},
            ],
        )

        result = CliRunner().invoke(
            cli_main.main, ["run", "--local", _repo(tmp_path), "--force"]
        )

        assert result.exit_code == 0
        assert captured["rollup_input"] == [{"file_path": "file0.py", "description": "ok"}]
        assert all("error" not in entry for entry in captured["readme_input"])

    def test_worker_level_errors_are_reported_too(self, monkeypatch, tmp_path):
        _patch_pipeline(
            monkeypatch,
            summaries=[{"file_path": "file0.py", "description": "ok"}],
            errors=[SummaryFailure("file1.py", "connection reset")],
        )

        result = CliRunner().invoke(
            cli_main.main, ["run", "--local", _repo(tmp_path), "--force"]
        )

        assert result.exit_code == 0
        assert "connection reset" in result.output
        assert "file1.py" in result.output

    def test_clean_run_prints_no_report(self, monkeypatch, tmp_path):
        _patch_pipeline(
            monkeypatch,
            summaries=[
                {"file_path": "file0.py", "description": "ok"},
                {"file_path": "file1.py", "description": "ok"},
            ],
        )

        result = CliRunner().invoke(
            cli_main.main, ["run", "--local", _repo(tmp_path), "--force"]
        )

        assert result.exit_code == 0
        assert "Summarization report" not in result.output

    def test_total_failure_aborts_instead_of_prompting_the_model(self, monkeypatch, tmp_path):
        captured = _patch_pipeline(
            monkeypatch,
            summaries=[
                {"file_path": "file0.py", "error": "boom"},
                {"file_path": "file1.py", "error": "boom"},
            ],
        )

        result = CliRunner().invoke(
            cli_main.main, ["run", "--local", _repo(tmp_path), "--force"]
        )

        assert result.exit_code == 1
        assert "Every file failed to summarize" in result.output
        assert "readme_input" not in captured

    def test_strict_fails_the_run_on_partial_failure(self, monkeypatch, tmp_path):
        _patch_pipeline(
            monkeypatch,
            summaries=[
                {"file_path": "file0.py", "description": "ok"},
                {"file_path": "file1.py", "error": "boom"},
            ],
        )

        result = CliRunner().invoke(
            cli_main.main, ["run", "--local", _repo(tmp_path), "--force", "--strict"]
        )

        assert result.exit_code == 1
        assert "--strict: 1 file(s) failed to summarize." in result.output

    def test_strict_still_writes_the_readme_before_failing(self, monkeypatch, tmp_path):
        _patch_pipeline(
            monkeypatch,
            summaries=[
                {"file_path": "file0.py", "description": "ok"},
                {"file_path": "file1.py", "error": "boom"},
            ],
            readme="# Partial README",
        )
        output = tmp_path / "OUT.md"

        result = CliRunner().invoke(
            cli_main.main,
            [
                "run",
                "--local",
                _repo(tmp_path),
                "--force",
                "--strict",
                "--output",
                str(output),
            ],
        )

        assert result.exit_code == 1
        assert output.read_text(encoding="utf-8") == "# Partial README"

    def test_strict_passes_when_nothing_failed(self, monkeypatch, tmp_path):
        _patch_pipeline(
            monkeypatch,
            summaries=[
                {"file_path": "file0.py", "description": "ok"},
                {"file_path": "file1.py", "description": "ok"},
            ],
        )

        result = CliRunner().invoke(
            cli_main.main, ["run", "--local", _repo(tmp_path), "--force", "--strict"]
        )

        assert result.exit_code == 0

    def test_temp_clone_is_still_cleaned_up_when_strict_fails(self, monkeypatch, tmp_path):
        _patch_pipeline(
            monkeypatch,
            summaries=[{"file_path": "file0.py", "error": "boom"}],
        )
        cleaned = []

        real_loader_cls = cli_main.RepoLoader

        class SpyLoader(real_loader_cls):
            def load(self, return_skip_info=False):
                result = super().load(return_skip_info=return_skip_info)
                loader_obj = result[2]
                original_cleanup = getattr(loader_obj, "cleanup", None)

                def cleanup():
                    cleaned.append(True)
                    if original_cleanup:
                        original_cleanup()

                loader_obj.cleanup = cleanup
                return result

        monkeypatch.setattr(cli_main, "RepoLoader", SpyLoader)

        result = CliRunner().invoke(
            cli_main.main, ["run", "--local", _repo(tmp_path, count=1), "--force"]
        )

        assert result.exit_code == 1
        assert cleaned == [True]
