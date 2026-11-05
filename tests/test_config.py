from repo2readme import config


def test_environment_api_key_is_used_without_prompting(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENV_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("GROQ_API_KEY", "environment-key-123")

    assert config.get_api_key("groq") == "environment-key-123"
    assert not (tmp_path / "missing.json").exists()


def test_environment_api_key_takes_precedence_over_saved_key(monkeypatch, tmp_path):
    env_path = tmp_path / "keys.json"
    monkeypatch.setattr(config, "ENV_PATH", str(env_path))
    config.save_env({"GROQ_API_KEY": "saved-key-123"})
    monkeypatch.setenv("GROQ_API_KEY", "environment-key-123")

    assert config.get_api_key("groq") == "environment-key-123"
