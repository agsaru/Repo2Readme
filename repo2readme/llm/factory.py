from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel

from repo2readme.llm.settings import DEFAULT_PROVIDER, LLMSettings
from repo2readme.providers import get_provider


def _missing_package(package: str, provider_label: str) -> ImportError:
    return ImportError(
        f"{provider_label} support requires the '{package}' package. "
        f"Install it with: pip install {package}"
    )


def create_llm_from_settings(
    settings: LLMSettings,
    api_key: str | None = None,
    **kwargs,
) -> BaseChatModel:
    """Build a chat model from already-resolved :class:`LLMSettings`.

    This is what every call site should use. The provider, model and base URL
    have been decided once for the whole run, so nothing here can apply a
    default that disagrees with what another part of the run decided.
    """
    return create_llm(
        provider=settings.provider,
        model=settings.model,
        api_key=api_key,
        base_url=settings.base_url,
        **kwargs,
    )


def create_llm(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs,
) -> BaseChatModel:
    """
    Factory function to create a LangChain chat model.

    Parameters
    ----------
    provider : str | None
        LLM provider name or alias, as listed in ``repo2readme.providers``.
        ``None`` means the project default (``groq``). Applying that fallback
        was left to each caller before, and they did not agree on it: the
        reviewer defaulted to Google while everything else defaulted to Groq.
    model : str | None
        Model name. Falls back to the provider's default model.
    api_key : str | None
        Optional API key. Falls back to the provider's environment variable.
    base_url : str | None
        Optional base URL. Falls back to the provider's default base URL,
        which is what makes the OpenAI-compatible providers work out of the box.

    Raises
    ------
    UnknownProviderError
        If the provider is not in the registry. The message lists every
        supported provider.
    """

    spec = get_provider(provider or DEFAULT_PROVIDER)
    name = spec.name
    model = model or spec.default_model
    base_url = base_url or spec.default_base_url
    resolved_key = api_key or (os.getenv(spec.env_var) if spec.env_var else None)

    if name == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:  # pragma: no cover - depends on install
            raise _missing_package("langchain-groq", spec.label) from exc
        return ChatGroq(model=model, api_key=resolved_key, **kwargs)

    if name == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:  # pragma: no cover - depends on install
            raise _missing_package("langchain-google-genai", spec.label) from exc
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=resolved_key,
            **kwargs,
        )

    if name == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - depends on install
            raise _missing_package("langchain-anthropic", spec.label) from exc
        return ChatAnthropic(model=model, api_key=resolved_key, **kwargs)

    if name == "ollama":
        # Ollama runs locally and needs no key, but langchain-ollama is not a
        # hard dependency, so fail with an actionable message.
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise _missing_package("langchain-ollama", spec.label) from exc
        return ChatOllama(model=model, base_url=base_url, **kwargs)

    # openai, openrouter and together all speak the OpenAI wire protocol and
    # differ only by base URL and key.
    if name in ("openai", "openrouter", "together"):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - depends on install
            raise _missing_package("langchain-openai", spec.label) from exc
        return ChatOpenAI(
            model=model,
            api_key=resolved_key,
            base_url=base_url,
            **kwargs,
        )

    # Unreachable while the registry and this function stay in sync; kept as a
    # guard so a newly registered provider fails loudly instead of silently.
    raise NotImplementedError(
        f"Provider {spec.name!r} is registered but has no factory branch."
    )
