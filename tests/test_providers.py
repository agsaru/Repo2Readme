import importlib

import pytest
from click.testing import CliRunner

from repo2readme import providers as providers_module
from repo2readme.providers import (
    PROVIDERS,
    ProviderSpec,
    UnknownProviderError,
    api_key_env_var,
    get_provider,
    is_supported,
    normalize_provider_name,
    provider_choices_help,
    requires_api_key,
    resolve_base_url,
    resolve_model,
    supported_providers,
)

cli_main = importlib.import_module("repo2readme.cli.main")


class TestRegistry:
    def test_every_previously_documented_provider_is_registered(self):
        # These were advertised in the --provider help text before the registry
        # existed; all of them must now resolve.
        for name in (
            "groq",
            "google",
            "openai",
            "anthropic",
            "openrouter",
            "together",
            "ollama",
        ):
            assert is_supported(name)

    def test_registry_entries_are_well_formed(self):
        for spec in PROVIDERS:
            assert isinstance(spec, ProviderSpec)
            assert spec.name == spec.name.lower()
            assert spec.label
            assert spec.default_model
            if spec.env_var is not None:
                assert spec.env_var.endswith("_API_KEY")

    def test_names_and_aliases_are_unique(self):
        keys = []
        for spec in PROVIDERS:
            keys.append(spec.name)
            keys.extend(spec.aliases)
        assert len(keys) == len(set(keys))

    def test_registry_index_rejects_duplicates(self):
        duplicated = (
            ProviderSpec(name="dup", label="Dup", default_model="m"),
            ProviderSpec(name="other", label="Other", default_model="m", aliases=("dup",)),
        )
        original = providers_module.PROVIDERS
        providers_module.PROVIDERS = duplicated
        try:
            with pytest.raises(RuntimeError, match="Duplicate provider key"):
                providers_module._build_index()
        finally:
            providers_module.PROVIDERS = original

    def test_supported_providers_listing(self):
        assert supported_providers() == [spec.name for spec in PROVIDERS]
        with_aliases = supported_providers(include_aliases=True)
        assert "gemini" in with_aliases
        assert with_aliases == sorted(with_aliases)

    def test_provider_choices_help_is_a_readable_list(self):
        help_text = provider_choices_help()
        assert "groq" in help_text
        assert "ollama" in help_text
        assert ", " in help_text


class TestLookup:
    def test_lookup_is_case_insensitive_and_trims(self):
        assert get_provider("  GROQ ").name == "groq"

    def test_aliases_resolve_to_canonical_name(self):
        assert normalize_provider_name("gemini") == "google"
        assert normalize_provider_name("claude") == "anthropic"

    @pytest.mark.parametrize("value", ["", "   ", None, "not-a-provider"])
    def test_unknown_provider_raises(self, value):
        with pytest.raises(UnknownProviderError):
            get_provider(value)

    def test_unknown_provider_message_lists_supported_providers(self):
        with pytest.raises(UnknownProviderError) as excinfo:
            get_provider("vertex")
        message = str(excinfo.value)
        assert "vertex" in message
        for name in supported_providers():
            assert name in message

    def test_unknown_provider_is_a_value_error(self):
        # Callers that used to catch ValueError keep working.
        assert issubclass(UnknownProviderError, ValueError)

    def test_is_supported_handles_empty_input(self):
        assert not is_supported(None)
        assert not is_supported("")


class TestDefaults:
    def test_api_key_env_var(self):
        assert api_key_env_var("gemini") == "GOOGLE_API_KEY"
        assert api_key_env_var("together") == "TOGETHER_API_KEY"

    def test_ollama_needs_no_api_key(self):
        assert api_key_env_var("ollama") is None
        assert requires_api_key("ollama") is False
        assert requires_api_key("groq") is True

    def test_resolve_model_prefers_explicit_value(self):
        assert resolve_model("groq", "my-model") == "my-model"
        assert resolve_model("groq", None) == get_provider("groq").default_model

    def test_resolve_base_url_falls_back_to_default(self):
        assert resolve_base_url("openrouter", None) == "https://openrouter.ai/api/v1"
        assert resolve_base_url("together", None) == "https://api.together.xyz/v1"
        assert resolve_base_url("openrouter", "http://proxy") == "http://proxy"

    def test_providers_without_default_base_url_return_none(self):
        assert resolve_base_url("groq", None) is None


class TestFactoryIntegration:
    def test_unknown_provider_raises_before_any_import(self):
        from repo2readme.llm.factory import create_llm

        with pytest.raises(UnknownProviderError):
            create_llm(provider="wat", model="x")

    def test_factory_covers_every_registered_provider(self):
        # Guards against registering a provider without a factory branch.
        import inspect

        from repo2readme.llm import factory

        source = inspect.getsource(factory.create_llm)
        for spec in PROVIDERS:
            assert f'"{spec.name}"' in source, f"no factory branch for {spec.name}"

    def test_openai_compatible_providers_get_their_base_url(self, monkeypatch):
        from repo2readme.llm import factory

        captured = {}

        class FakeChatOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        fake_module = type("mod", (), {"ChatOpenAI": FakeChatOpenAI})
        monkeypatch.setitem(
            __import__("sys").modules, "langchain_openai", fake_module
        )
        monkeypatch.setenv("TOGETHER_API_KEY", "together-key")

        factory.create_llm(provider="together")

        assert captured["base_url"] == "https://api.together.xyz/v1"
        assert captured["api_key"] == "together-key"
        assert captured["model"] == get_provider("together").default_model

    def test_explicit_base_url_overrides_provider_default(self, monkeypatch):
        from repo2readme.llm import factory

        captured = {}

        class FakeChatOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        fake_module = type("mod", (), {"ChatOpenAI": FakeChatOpenAI})
        monkeypatch.setitem(
            __import__("sys").modules, "langchain_openai", fake_module
        )

        factory.create_llm(
            provider="openrouter", model="m", api_key="k", base_url="http://local"
        )

        assert captured["base_url"] == "http://local"
        assert captured["model"] == "m"

    def test_ollama_reports_missing_package_clearly(self, monkeypatch):
        import builtins

        from repo2readme.llm import factory

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langchain_ollama":
                raise ImportError("No module named 'langchain_ollama'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        with pytest.raises(ImportError, match="pip install langchain-ollama"):
            factory.create_llm(provider="ollama")


class TestApiKeyResolution:
    def test_keyless_provider_does_not_prompt(self, monkeypatch, tmp_path):
        from repo2readme import config

        monkeypatch.setattr(config, "ENV_PATH", str(tmp_path / "env.json"))

        def fail(*args, **kwargs):
            raise AssertionError("ollama must not prompt for an API key")

        monkeypatch.setattr(config, "click", type("c", (), {"prompt": fail}))

        assert config.get_api_key("ollama") is None

    def test_alias_reads_the_canonical_env_var(self, monkeypatch, tmp_path):
        import json

        from repo2readme import config

        env_file = tmp_path / "env.json"
        env_file.write_text(json.dumps({"GOOGLE_API_KEY": "google-secret"}))
        monkeypatch.setattr(config, "ENV_PATH", str(env_file))
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        assert config.get_api_key("gemini") == "google-secret"

    def test_setup_api_keys_exports_provider_env_var(self, monkeypatch):
        from repo2readme.services import environment

        monkeypatch.setattr(environment, "get_api_key", lambda name: "secret")
        monkeypatch.delenv("TOGETHER_API_KEY", raising=False)

        environment.setup_api_keys("together")

        import os

        assert os.environ["TOGETHER_API_KEY"] == "secret"

    def test_setup_api_keys_skips_keyless_provider(self, monkeypatch):
        from repo2readme.services import environment

        def fail(name):
            raise AssertionError("should not resolve a key for ollama")

        monkeypatch.setattr(environment, "get_api_key", fail)

        environment.setup_api_keys("ollama")

    def test_setup_api_keys_rejects_unknown_provider(self):
        from repo2readme.services import environment

        with pytest.raises(UnknownProviderError):
            environment.setup_api_keys("nope")


class TestProvidersCommand:
    def test_providers_command_lists_every_provider(self):
        runner = CliRunner()
        result = runner.invoke(cli_main.main, ["providers"], terminal_width=200)

        assert result.exit_code == 0
        for spec in PROVIDERS:
            assert spec.name in result.output
        assert "not required" in result.output

    def test_run_help_lists_providers_from_the_registry(self):
        runner = CliRunner()
        result = runner.invoke(cli_main.main, ["run", "--help"], terminal_width=200)

        assert result.exit_code == 0
        assert "groq" in result.output
        assert "ollama" in result.output
