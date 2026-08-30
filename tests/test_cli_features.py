import importlib
import os
from click.testing import CliRunner
import pytest

cli_main = importlib.import_module("repo2readme.cli.main")


def test_dry_run_mode(monkeypatch, tmp_path):
    # Create some dummy files in tmp_path
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')", encoding="utf-8")
    
    file2 = tmp_path / "utils.py"
    file2.write_text("def add(a, b): return a + b", encoding="utf-8")

    # In dry-run, we should NOT ask for API keys or run summarize/workflow.
    # We will patch them just in case they are called (to make the test fail if they are called).
    def error_setup_api_keys(*settings):
        raise Exception("API keys should not be requested in dry-run mode")

    monkeypatch.setattr(cli_main, "setup_api_keys", error_setup_api_keys)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["run", "--local", str(tmp_path), "--dry-run"],
    )

    assert result.exit_code == 0
    assert "Repository Analysis" in result.output
    assert "Files selected     : 2" in result.output
    # main.py length is 14 -> ~4 tokens. utils.py length is 27 -> ~9 tokens. Total tokens -> ~13
    assert "Estimated tokens   : ~13" in result.output
    assert "Repository Tree" in result.output
    assert "Files to be processed" in result.output
    assert "✓ main.py" in result.output
    assert "✓ utils.py" in result.output
    assert "Dry run complete." in result.output
    assert "No API requests were made." in result.output


def test_dry_run_shows_skipped_files(monkeypatch, tmp_path):
    # Create some files including ones that should be skipped
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')", encoding="utf-8")
    
    file2 = tmp_path / "README.md"
    file2.write_text("# README", encoding="utf-8")
    
    file3 = tmp_path / "large.py"
    file3.write_text("x" * 2000, encoding="utf-8")  # Exceeds 1 KB limit
    
    file4 = tmp_path / "node_modules"
    file4.mkdir()
    file5 = file4 / "package.json"
    file5.write_text("{}", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        [
            "run",
            "--local", str(tmp_path),
            "--dry-run",
            "--exclude", "*.md",
            "--max-file-size-kb", "1"
        ],
    )

    assert result.exit_code == 0
    assert "Skipped Files Summary" in result.output
    assert "excluded by pattern" in result.output
    assert "exceeds maximum file size" in result.output
    assert "ignored by default rules" in result.output

def test_dry_run_shows_unknown_skip_reasons(monkeypatch, tmp_path):
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')", encoding="utf-8")

    import repo2readme.loaders.repo_loader as rl_module
    original_load = rl_module.RepoLoader.load

    def fake_load(self, return_skip_info=False):
        docs, root_path, loader = original_load(self, return_skip_info=False)
        skipped = [
            ("README.md", "excluded by pattern"),
            ("custom.txt", "my custom reason"),
        ] if return_skip_info else []
        if return_skip_info:
            return docs, root_path, loader, skipped
        return docs, root_path, loader

    monkeypatch.setattr(rl_module.RepoLoader, "load", fake_load)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["run", "--local", str(tmp_path), "--dry-run"],
    )

    assert result.exit_code == 0
    assert "Skipped Files Summary" in result.output
    assert "excluded by pattern" in result.output
    assert "my custom reason" in result.output


def test_normal_run_user_declines(monkeypatch, tmp_path):
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')", encoding="utf-8")

    def error_setup_api_keys(*settings):
        raise Exception("API keys should not be requested if user declines")

    monkeypatch.setattr(cli_main, "setup_api_keys", error_setup_api_keys)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["run", "--local", str(tmp_path)],
        input="n\n", # Decline the confirmation prompt
    )

    assert result.exit_code == 0
    assert "Repository Analysis" in result.output
    assert "Files to summarize : 1" in result.output
    assert "Proceed?" in result.output
    assert "Operation cancelled." in result.output


def test_normal_run_user_confirms(monkeypatch, tmp_path):
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')", encoding="utf-8")

    api_keys_called = False
    summarize_called = False
    workflow_called = False

    def fake_setup_api_keys(*settings):
        nonlocal api_keys_called
        api_keys_called = True

    def fake_generate_all_summaries(documents, summary_cache, provider, model, base_url, progress, task_id, **kwargs):
        nonlocal summarize_called
        summarize_called = True
        return [{"file_path": "main.py", "description": "fake summary"}], []

    def fake_generate_hierarchical_summaries(file_summaries, provider, model, base_url, progress, task_id):
        return file_summaries

    def fake_run_pipeline(summaries, tree, dependency_overview, settings=None, reviewer_settings=None):
        nonlocal workflow_called
        workflow_called = True
        return "fake readme contents"

    monkeypatch.setattr(cli_main, "setup_api_keys", fake_setup_api_keys)
    monkeypatch.setattr(cli_main, "generate_all_summaries", fake_generate_all_summaries)
    monkeypatch.setattr(cli_main, "generate_hierarchical_summaries", fake_generate_hierarchical_summaries)
    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["run", "--local", str(tmp_path)],
        input="y\n", # Confirm the prompt
    )

    assert result.exit_code == 0
    assert "Repository Analysis" in result.output
    assert "Files to summarize : 1" in result.output
    assert "Proceed?" in result.output
    assert "Generating summaries..." in result.output
    assert "Generating README..." in result.output
    assert "Generated README:" in result.output
    assert "fake readme contents" in result.output
    assert api_keys_called is True
    assert summarize_called is True
    assert workflow_called is True


def test_normal_run_force_bypasses_confirmation(monkeypatch, tmp_path):
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')", encoding="utf-8")

    api_keys_called = False
    summarize_called = False
    workflow_called = False

    def fake_setup_api_keys(*settings):
        nonlocal api_keys_called
        api_keys_called = True

    def fake_generate_all_summaries(documents, summary_cache, provider, model, base_url, progress, task_id, **kwargs):
        nonlocal summarize_called
        summarize_called = True
        return [{"file_path": "main.py", "description": "fake summary"}], []

    def fake_generate_hierarchical_summaries(file_summaries, provider, model, base_url, progress, task_id):
        return file_summaries

    def fake_run_pipeline(summaries, tree, dependency_overview, settings=None, reviewer_settings=None):
        nonlocal workflow_called
        workflow_called = True
        return "fake readme contents"

    monkeypatch.setattr(cli_main, "setup_api_keys", fake_setup_api_keys)
    monkeypatch.setattr(cli_main, "generate_all_summaries", fake_generate_all_summaries)
    monkeypatch.setattr(cli_main, "generate_hierarchical_summaries", fake_generate_hierarchical_summaries)
    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["run", "--local", str(tmp_path), "--force"],
    )

    assert result.exit_code == 0
    assert "Repository Analysis" in result.output
    assert "Files to summarize : 1" in result.output
    assert "Proceed?" not in result.output # Should not prompt
    assert "Generating summaries..." in result.output
    assert "Generating README..." in result.output
    assert api_keys_called is True
    assert summarize_called is True
    assert workflow_called is True