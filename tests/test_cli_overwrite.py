import importlib

from click.testing import CliRunner


cli_main = importlib.import_module("repo2readme.cli.main")


def test_output_file_is_not_overwritten_when_user_declines(monkeypatch, tmp_path):
    output_file = tmp_path / "README.md"
    output_file.write_text("existing content", encoding="utf-8")

    def fake_get_api_keys():
        return "fake_groq_key", "fake_gemini_key"

    class FakeRepoLoader:
        def __init__(self, source, *args, **kwargs):
            self.source = source

        def load(self):
            return [], str(tmp_path), None

    class FakeWorkflow:
        def invoke(self, state):
            return {"best_readme": "new generated content"}

    monkeypatch.setattr(cli_main, "get_api_keys", fake_get_api_keys)
    monkeypatch.setattr("repo2readme.loaders.repo_loader.RepoLoader", FakeRepoLoader)
    monkeypatch.setattr("repo2readme.readme.agent_workflow.workflow", FakeWorkflow())

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["run", "--local", str(tmp_path), "--output", str(output_file)],
        input="y\nn\n",
    )

    assert result.exit_code == 0
    assert output_file.read_text(encoding="utf-8") == "existing content"
    assert "not overwritten" in result.output


def test_output_file_is_overwritten_when_user_confirms(monkeypatch, tmp_path):
    output_file = tmp_path / "README.md"
    output_file.write_text("existing content", encoding="utf-8")

    def fake_get_api_keys():
        return "fake_groq_key", "fake_gemini_key"

    class FakeRepoLoader:
        def __init__(self, source, *args, **kwargs):
            self.source = source

        def load(self):
            return [], str(tmp_path), None

    class FakeWorkflow:
        def invoke(self, state):
            return {"best_readme": "new generated content"}

    monkeypatch.setattr(cli_main, "get_api_keys", fake_get_api_keys)
    monkeypatch.setattr("repo2readme.loaders.repo_loader.RepoLoader", FakeRepoLoader)
    monkeypatch.setattr("repo2readme.readme.agent_workflow.workflow", FakeWorkflow())

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        ["run", "--local", str(tmp_path), "--output", str(output_file)],
        input="y\ny\n",
    )

    assert result.exit_code == 0
    assert output_file.read_text(encoding="utf-8") == "new generated content"
    assert "Saved to" in result.output


def test_output_file_is_overwritten_with_force(monkeypatch, tmp_path):
    output_file = tmp_path / "README.md"
    output_file.write_text("existing content", encoding="utf-8")

    def fake_get_api_keys():
        return "fake_groq_key", "fake_gemini_key"

    class FakeRepoLoader:
        def __init__(self, source, *args, **kwargs):
            self.source = source

        def load(self):
            return [], str(tmp_path), None

    class FakeWorkflow:
        def invoke(self, state):
            return {"best_readme": "new generated content"}

    monkeypatch.setattr(cli_main, "get_api_keys", fake_get_api_keys)
    monkeypatch.setattr("repo2readme.loaders.repo_loader.RepoLoader", FakeRepoLoader)
    monkeypatch.setattr("repo2readme.readme.agent_workflow.workflow", FakeWorkflow())

    runner = CliRunner()
    result = runner.invoke(
        cli_main.main,
        [
            "run",
            "--local",
            str(tmp_path),
            "--output",
            str(output_file),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert output_file.read_text(encoding="utf-8") == "new generated content"
    assert "Saved to" in result.output