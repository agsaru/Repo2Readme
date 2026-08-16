"""Tests for resolving the provider, model and base URL once per run.

The behaviour under test is the one from the issue: every LLM call site applied
its own default provider - Groq for the summarizer, the roll-up and the
generator, Google for the reviewer - so a run without ``--provider`` talked to
two vendors, needed two API keys, and handed the same ``--model`` to both.
"""

import importlib
import os
import sys

import pytest
from click.testing import CliRunner

from repo2readme.llm.settings import (
    DEFAULT_PROVIDER,
    LLMSettings,
    UnknownProviderError,
    required_api_keys,
    resolve_reviewer_settings,
    resolve_settings,
    validate_providers,
)
from repo2readme.providers import get_provider
from repo2readme.services import environment

cli_main = importlib.import_module("repo2readme.cli.main")

# ---------------------------------------------------------------------------
# resolve_settings
# ---------------------------------------------------------------------------


def test_no_flags_resolve_to_the_project_default():
    settings = resolve_settings()

    assert settings.provider == DEFAULT_PROVIDER
    assert settings.model == get_provider(DEFAULT_PROVIDER).default_model
    assert settings.env_var == "GROQ_API_KEY"
    assert settings.requires_api_key is True


def test_an_alias_resolves_to_the_canonical_name():
    assert resolve_settings("gemini").provider == "google"
    assert resolve_settings("claude").provider == "anthropic"


def test_an_explicit_model_wins_over_the_provider_default():
    settings = resolve_settings("google", "gemini-2.5-pro")

    assert settings.provider == "google"
    assert settings.model == "gemini-2.5-pro"


def test_the_provider_default_base_url_is_applied():
    assert resolve_settings("openrouter").base_url == "https://openrouter.ai/api/v1"
    assert resolve_settings("together").base_url == "https://api.together.xyz/v1"
    assert resolve_settings("groq").base_url is None


def test_an_explicit_base_url_wins():
    settings = resolve_settings("openrouter", base_url="http://localhost:8080/v1")

    assert settings.base_url == "http://localhost:8080/v1"


def test_a_keyless_provider_is_marked_as_such():
    settings = resolve_settings("ollama")

    assert settings.requires_api_key is False
    assert settings.env_var is None


def test_an_unknown_provider_is_rejected():
    with pytest.raises(UnknownProviderError):
        resolve_settings("grok")


def test_describe_names_what_will_be_called():
    assert resolve_settings("groq").describe().startswith("Groq (")
    assert "https://openrouter.ai/api/v1" in resolve_settings("openrouter").describe()


def test_settings_are_comparable_and_hashable():
    assert resolve_settings("groq") == resolve_settings("groq")
    assert resolve_settings("gemini") == resolve_settings("google")
    assert resolve_settings("groq") != resolve_settings("google")
    assert len({resolve_settings("groq"), resolve_settings("groq")}) == 1


def test_replace_re_resolves_consistently():
    settings = resolve_settings("groq")
    moved = settings.replace(provider="google", model=None)

    assert moved.provider == "google"
    assert moved.label == "Google Gemini"
    assert moved.env_var == "GOOGLE_API_KEY"


# ---------------------------------------------------------------------------
# The cache identity
# ---------------------------------------------------------------------------


def test_the_cache_config_uses_the_resolved_values():
    explicit = resolve_settings("groq").as_cache_config()
    implicit = resolve_settings().as_cache_config()

    # The same run either way, so the same cache - this used to hash
    # {"provider": None} against {"provider": "groq"} and invalidate itself.
    assert explicit == implicit
    assert explicit["provider"] == "groq"
    assert explicit["model"] == get_provider("groq").default_model


def test_an_alias_does_not_change_the_cache_identity():
    assert resolve_settings("gemini").as_cache_config() == (
        resolve_settings("google").as_cache_config()
    )


def test_a_different_model_changes_the_cache_identity():
    assert resolve_settings("groq", "a").as_cache_config() != (
        resolve_settings("groq", "b").as_cache_config()
    )


# ---------------------------------------------------------------------------
# resolve_reviewer_settings - the core of the bug
# ---------------------------------------------------------------------------


def test_the_reviewer_follows_the_run_by_default():
    main = resolve_settings("groq", "llama-3.3-70b-versatile")

    assert resolve_reviewer_settings(main) == main


def test_the_reviewer_no_longer_jumps_to_google():
    # The reviewer defaulted to Google while everything else defaulted to Groq.
    main = resolve_settings()

    assert resolve_reviewer_settings(main).provider == "groq"


def test_a_model_is_not_carried_to_another_vendor():
    main = resolve_settings("groq", "llama-3.3-70b-versatile")

    reviewer = resolve_reviewer_settings(main, provider="google")

    assert reviewer.provider == "google"
    # A Groq model name means nothing to Google; the reviewer gets Google's own
    # default instead. This is the exact failure the issue describes.
    assert reviewer.model == get_provider("google").default_model


def test_an_explicit_reviewer_model_is_used_as_given():
    main = resolve_settings("groq")

    reviewer = resolve_reviewer_settings(
        main, provider="google", model="gemini-2.5-pro"
    )

    assert (reviewer.provider, reviewer.model) == ("google", "gemini-2.5-pro")


def test_the_same_vendor_inherits_the_model():
    main = resolve_settings("groq", "llama-3.3-70b-versatile")

    reviewer = resolve_reviewer_settings(main, provider="groq")

    assert reviewer == main


def test_a_reviewer_model_alone_stays_on_the_run_s_provider():
    main = resolve_settings("groq")

    reviewer = resolve_reviewer_settings(main, model="openai/gpt-oss-20b")

    assert reviewer.provider == "groq"
    assert reviewer.model == "openai/gpt-oss-20b"


def test_a_reviewer_base_url_alone_stays_on_the_run_s_provider():
    main = resolve_settings("openai")

    reviewer = resolve_reviewer_settings(main, base_url="http://localhost:1234/v1")

    assert reviewer.provider == "openai"
    assert reviewer.model == main.model
    assert reviewer.base_url == "http://localhost:1234/v1"


def test_an_unknown_reviewer_provider_is_rejected():
    with pytest.raises(UnknownProviderError):
        resolve_reviewer_settings(resolve_settings(), provider="nope")


# ---------------------------------------------------------------------------
# validate_providers / required_api_keys
# ---------------------------------------------------------------------------


def test_validate_providers_accepts_names_aliases_and_none():
    validate_providers(None, "groq", "gemini", "")


def test_validate_providers_rejects_a_typo():
    with pytest.raises(UnknownProviderError) as exc_info:
        validate_providers("groq", "grok")

    assert "grok" in str(exc_info.value)
    assert "Supported providers" in str(exc_info.value)


def test_one_vendor_needs_one_key():
    main = resolve_settings("groq")

    needed = required_api_keys(main, resolve_reviewer_settings(main))

    assert [s.provider for s in needed] == ["groq"]


def test_two_vendors_need_two_keys():
    main = resolve_settings("groq")
    reviewer = resolve_reviewer_settings(main, provider="google")

    assert [s.provider for s in required_api_keys(main, reviewer)] == [
        "groq",
        "google",
    ]


def test_a_keyless_provider_needs_nothing():
    assert required_api_keys(resolve_settings("ollama")) == []


def test_none_entries_are_ignored():
    assert required_api_keys(None, None) == []


# ---------------------------------------------------------------------------
# setup_api_keys
# ---------------------------------------------------------------------------


class TestSetupApiKeys:
    def test_a_single_vendor_run_asks_for_one_key(self, monkeypatch):
        asked = []

        def fake_get_api_key(name):
            asked.append(name)
            return "secret"

        monkeypatch.setattr(environment, "get_api_key", fake_get_api_key)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        main = resolve_settings()
        environment.setup_api_keys(main, resolve_reviewer_settings(main))

        assert asked == ["groq"]
        assert os.environ["GROQ_API_KEY"] == "secret"

    def test_two_vendors_ask_for_both(self, monkeypatch):
        asked = []
        monkeypatch.setattr(
            environment, "get_api_key", lambda name: asked.append(name) or "secret"
        )

        main = resolve_settings("groq")
        environment.setup_api_keys(
            main, resolve_reviewer_settings(main, provider="google")
        )

        assert asked == ["groq", "google"]

    def test_a_provider_name_still_works(self, monkeypatch):
        monkeypatch.setattr(environment, "get_api_key", lambda name: "secret")
        monkeypatch.delenv("TOGETHER_API_KEY", raising=False)

        environment.setup_api_keys("together")

        assert os.environ["TOGETHER_API_KEY"] == "secret"

    def test_a_keyless_provider_is_never_asked(self, monkeypatch):
        def fail(name):
            raise AssertionError("should not resolve a key for ollama")

        monkeypatch.setattr(environment, "get_api_key", fail)

        environment.setup_api_keys(resolve_settings("ollama"))


# ---------------------------------------------------------------------------
# The call sites
# ---------------------------------------------------------------------------


class TestCallSites:
    def test_no_call_site_carries_its_own_provider_default(self):
        import inspect

        from repo2readme.readme import readme_generator, reviewer_agent
        from repo2readme.summarize import directory_summary, summary

        for module in (summary, directory_summary, readme_generator, reviewer_agent):
            source = inspect.getsource(module)
            assert 'provider or "groq"' not in source, module.__name__
            assert 'provider or "google"' not in source, module.__name__

    def test_the_factory_applies_the_only_default(self, monkeypatch):
        from repo2readme.llm import factory

        seen = {}

        class FakeChatGroq:
            def __init__(self, **kwargs):
                seen.update(kwargs)

        monkeypatch.setitem(
            sys.modules, "langchain_groq", type("mod", (), {"ChatGroq": FakeChatGroq})
        )

        factory.create_llm(provider=None)

        assert seen["model"] == get_provider(DEFAULT_PROVIDER).default_model

    def test_create_llm_from_settings_passes_everything_through(self, monkeypatch):
        from repo2readme.llm import factory

        seen = {}

        class FakeChatOpenAI:
            def __init__(self, **kwargs):
                seen.update(kwargs)

        monkeypatch.setitem(
            sys.modules,
            "langchain_openai",
            type("mod", (), {"ChatOpenAI": FakeChatOpenAI}),
        )

        settings = LLMSettings(
            provider="openrouter",
            model="some/model",
            base_url="https://example.invalid/v1",
            label="OpenRouter",
            env_var="OPENROUTER_API_KEY",
        )
        factory.create_llm_from_settings(settings)

        assert seen["model"] == "some/model"
        assert seen["base_url"] == "https://example.invalid/v1"

    def test_an_unknown_provider_still_raises(self):
        from repo2readme.llm import factory

        with pytest.raises(UnknownProviderError):
            factory.create_llm(provider="wat")


class TestWorkflowState:
    def test_the_reviewer_node_uses_the_reviewer_settings(self, monkeypatch):
        from repo2readme.readme import agent_workflow

        seen = {}

        class FakeReview:
            score = 9.0
            feedback = "fine"

        def fake_reviewer(readme, provider=None, model_name=None, base_url=None):
            seen.update(
                provider=provider, model_name=model_name, base_url=base_url
            )
            return FakeReview()

        monkeypatch.setattr(agent_workflow, "readme_reviewer", fake_reviewer)

        agent_workflow.readme_reviewer_node(
            {
                "readme": ["# Title"],
                "best_score": 0.0,
                "best_readme": "",
                "iteration_no": 0,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "base_url": None,
                "reviewer_provider": "google",
                "reviewer_model": "gemini-2.5-flash",
                "reviewer_base_url": None,
            }
        )

        assert seen["provider"] == "google"
        assert seen["model_name"] == "gemini-2.5-flash"

    def test_the_reviewer_node_falls_back_to_the_run_settings(self, monkeypatch):
        from repo2readme.readme import agent_workflow

        seen = {}

        class FakeReview:
            score = 9.0
            feedback = "fine"

        def fake_reviewer(readme, provider=None, model_name=None, base_url=None):
            seen.update(provider=provider, model_name=model_name)
            return FakeReview()

        monkeypatch.setattr(agent_workflow, "readme_reviewer", fake_reviewer)

        agent_workflow.readme_reviewer_node(
            {
                "readme": ["# Title"],
                "best_score": 0.0,
                "best_readme": "",
                "iteration_no": 0,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "base_url": None,
                "reviewer_provider": None,
                "reviewer_model": None,
                "reviewer_base_url": None,
            }
        )

        assert seen["provider"] == "groq"
        assert seen["model_name"] == "llama-3.3-70b-versatile"


class TestOrchestratorWiring:
    def test_the_workflow_state_carries_both_settings(self, monkeypatch):
        from repo2readme.services import orchestrator

        captured = {}

        class FakeWorkflow:
            def invoke(self, state):
                captured.update(state)
                return {"best_readme": "# Title\n"}

        monkeypatch.setattr(orchestrator, "build_workflow", lambda: FakeWorkflow())

        main = resolve_settings("groq", "llama-3.3-70b-versatile")
        orchestrator.run_pipeline(
            summaries=[],
            tree="",
            dependency_overview="",
            settings=main,
            reviewer_settings=resolve_reviewer_settings(main, provider="google"),
        )

        assert captured["provider"] == "groq"
        assert captured["model"] == "llama-3.3-70b-versatile"
        assert captured["reviewer_provider"] == "google"
        assert captured["reviewer_model"] == get_provider("google").default_model

    def test_the_reviewer_defaults_to_the_run_settings(self, monkeypatch):
        from repo2readme.services import orchestrator

        captured = {}

        class FakeWorkflow:
            def invoke(self, state):
                captured.update(state)
                return {"best_readme": "# Title\n"}

        monkeypatch.setattr(orchestrator, "build_workflow", lambda: FakeWorkflow())

        orchestrator.run_pipeline(summaries=[], tree="", dependency_overview="")

        assert captured["reviewer_provider"] == captured["provider"]
        assert captured["reviewer_model"] == captured["model"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_a_provider_typo_fails_before_anything_is_loaded(self, monkeypatch, tmp_path):
        def fail(*args, **kwargs):
            raise AssertionError("the repository must not be loaded")

        monkeypatch.setattr(cli_main, "RepoLoader", fail)

        result = CliRunner().invoke(
            cli_main.main,
            ["run", "--local", str(tmp_path), "--provider", "grok"],
        )

        assert result.exit_code == 2
        assert "grok" in result.output
        assert "Supported providers" in result.output

    def test_a_reviewer_provider_typo_fails_too(self, monkeypatch, tmp_path):
        def fail(*args, **kwargs):
            raise AssertionError("the repository must not be loaded")

        monkeypatch.setattr(cli_main, "RepoLoader", fail)

        result = CliRunner().invoke(
            cli_main.main,
            ["run", "--local", str(tmp_path), "--reviewer-provider", "nope"],
        )

        assert result.exit_code == 2

    def test_the_resolved_model_is_reported(self, tmp_path):
        (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")

        result = CliRunner().invoke(
            cli_main.main,
            ["run", "--local", str(tmp_path), "--dry-run", "--provider", "ollama"],
        )

        assert result.exit_code == 0
        assert "Ollama" in result.output

    def test_the_reviewer_line_only_appears_when_it_differs(self, tmp_path):
        (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")

        same = CliRunner().invoke(
            cli_main.main, ["run", "--local", str(tmp_path), "--dry-run"]
        )
        different = CliRunner().invoke(
            cli_main.main,
            [
                "run",
                "--local",
                str(tmp_path),
                "--dry-run",
                "--reviewer-provider",
                "google",
            ],
        )

        assert "Reviewer" not in same.output
        assert "Reviewer" in different.output
