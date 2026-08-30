import importlib

from click.testing import CliRunner


cli_main = importlib.import_module("repo2readme.cli.main")


def test_output_file_is_not_overwritten_when_user_declines(monkeypatch, tmp_path):
    output_file = tmp_path / "README.md"
    output_file.write_text("existing content", encoding="utf-8")

    def fake_setup_api_keys(*settings):
        pass

    class FakeRepoLoader:
        def __init__(self, source, *args, **kwargs):
            self.source = source

        def load(self):
            return [], str(tmp_path), None

    def fake_generate_all_summaries(documents, summary_cache, **kwargs):
        return [{"file_path": "main.py", "description": "entry point"}], []

    def fake_generate_hierarchical_summaries(file_summaries, provider, model, base_url, progress, task_id):
        return file_summaries

    def fake_run_pipeline(summaries, tree, dependency_overview, settings=None, reviewer_settings=None):
        return "new generated content"

    monkeypatch.setattr(cli_main, "setup_api_keys", fake_setup_api_keys)
    monkeypatch.setattr("repo2readme.loaders.repo_loader.RepoLoader", FakeRepoLoader)
    monkeypatch.setattr(cli_main, "generate_all_summaries", fake_generate_all_summaries)
    monkeypatch.setattr(cli_main, "generate_hierarchical_summaries", fake_generate_hierarchical_summaries)
    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

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

    def fake_setup_api_keys(*settings):
        pass

    class FakeRepoLoader:
        def __init__(self, source, *args, **kwargs):
            self.source = source

        def load(self):
            return [], str(tmp_path), None

    def fake_generate_all_summaries(documents, summary_cache, **kwargs):
        return [{"file_path": "main.py", "description": "entry point"}], []

    def fake_generate_hierarchical_summaries(file_summaries, provider, model, base_url, progress, task_id):
        return file_summaries

    def fake_run_pipeline(summaries, tree, dependency_overview, settings=None, reviewer_settings=None):
        return "new generated content"

    monkeypatch.setattr(cli_main, "setup_api_keys", fake_setup_api_keys)
    monkeypatch.setattr("repo2readme.loaders.repo_loader.RepoLoader", FakeRepoLoader)
    monkeypatch.setattr(cli_main, "generate_all_summaries", fake_generate_all_summaries)
    monkeypatch.setattr(cli_main, "generate_hierarchical_summaries", fake_generate_hierarchical_summaries)
    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

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

    def fake_setup_api_keys(*settings):
        pass

    class FakeRepoLoader:
        def __init__(self, source, *args, **kwargs):
            self.source = source

        def load(self):
            return [], str(tmp_path), None

    def fake_generate_all_summaries(documents, summary_cache, **kwargs):
        return [{"file_path": "main.py", "description": "entry point"}], []

    def fake_generate_hierarchical_summaries(file_summaries, provider, model, base_url, progress, task_id):
        return file_summaries

    def fake_run_pipeline(summaries, tree, dependency_overview, settings=None, reviewer_settings=None):
        return "new generated content"

    monkeypatch.setattr(cli_main, "setup_api_keys", fake_setup_api_keys)
    monkeypatch.setattr("repo2readme.loaders.repo_loader.RepoLoader", FakeRepoLoader)
    monkeypatch.setattr(cli_main, "generate_all_summaries", fake_generate_all_summaries)
    monkeypatch.setattr(cli_main, "generate_hierarchical_summaries", fake_generate_hierarchical_summaries)
    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

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