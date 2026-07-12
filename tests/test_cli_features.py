import importlib
from click.testing import CliRunner

cli_main = importlib.import_module("repo2readme.cli.main")


def test_dry_run_mode(monkeypatch, tmp_path):
    # Create some dummy files in tmp_path
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')", encoding="utf-8")
    
    file2 = tmp_path / "utils.py"
    file2.write_text("def add(a, b): return a + b", encoding="utf-8")

    # In dry-run, we should NOT ask for API keys or run summarize/workflow.
    # We will patch them just in case they are called (to make the test fail if they are called).
    def error_get_api_keys():
        raise Exception("API keys should not be requested in dry-run mode")

    monkeypatch.setattr(cli_main, "get_api_keys", error_get_api_keys)

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


def test_normal_run_user_declines(monkeypatch, tmp_path):
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')", encoding="utf-8")

    def error_get_api_keys():
        raise Exception("API keys should not be requested if user declines")

    monkeypatch.setattr(cli_main, "get_api_keys", error_get_api_keys)

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

    def fake_get_api_keys():
        nonlocal api_keys_called
        api_keys_called = True
        return "fake_groq", "fake_gemini"

    def fake_summarize_file(file_path, language, content):
        nonlocal summarize_called
        summarize_called = True
        return {"file_path": file_path, "description": "fake summary"}

    class FakeWorkflow:
        def invoke(self, state):
            nonlocal workflow_called
            workflow_called = True
            return {"best_readme": "fake readme contents"}

    monkeypatch.setattr(cli_main, "get_api_keys", fake_get_api_keys)
    monkeypatch.setattr("repo2readme.summarize.summary.summarize_file", fake_summarize_file)
    monkeypatch.setattr("repo2readme.readme.agent_workflow.workflow", FakeWorkflow())

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

    def fake_get_api_keys():
        nonlocal api_keys_called
        api_keys_called = True
        return "fake_groq", "fake_gemini"

    def fake_summarize_file(file_path, language, content):
        nonlocal summarize_called
        summarize_called = True
        return {"file_path": file_path, "description": "fake summary"}

    class FakeWorkflow:
        def invoke(self, state):
            nonlocal workflow_called
            workflow_called = True
            return {"best_readme": "fake readme contents"}

    monkeypatch.setattr(cli_main, "get_api_keys", fake_get_api_keys)
    monkeypatch.setattr("repo2readme.summarize.summary.summarize_file", fake_summarize_file)
    monkeypatch.setattr("repo2readme.readme.agent_workflow.workflow", FakeWorkflow())

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