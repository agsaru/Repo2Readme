import importlib
import os
from click.testing import CliRunner

cli_main = importlib.import_module("repo2readme.cli.main")


def test_reset_when_env_missing(monkeypatch, tmp_path):
    # Ensure reset_api_keys removes ENV_PATH if exists and reports accordingly
    # Monkeypatch ENV_PATH to a temp file location
    import repo2readme.config as cfg

    monkeypatch.setattr(cfg, "ENV_PATH", str(tmp_path / "env.json"))

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["reset"]) 

    assert result.exit_code == 0
    assert "No API key file found to reset." in result.output


def test_reset_when_env_exists(monkeypatch, tmp_path):
    import repo2readme.config as cfg

    env_file = tmp_path / "env.json"
    env_file.write_text('{}', encoding='utf-8')

    monkeypatch.setattr(cfg, "ENV_PATH", str(env_file))

    runner = CliRunner()
    result = runner.invoke(cli_main.main, ["reset"]) 

    assert result.exit_code == 0
    assert "API keys reset successfully!" in result.output
