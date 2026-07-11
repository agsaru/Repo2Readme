from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel

def create_llm(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs,
) -> BaseChatModel:
    """
    Factory function to create a LangChain chat model.

    Parameters
    ----------
    provider : str
        LLM provider name.
    model : str
        Model name.
    api_key : str | None
        Optional API key. Falls back to environment variable.
    base_url : str | None
        Optional base URL for OpenAI-compatible APIs.
    """

    provider = provider.lower()

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            api_key=api_key or os.getenv("GROQ_API_KEY"),
            **kwargs,
        )

    elif provider in ("google", "gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key or os.getenv("GOOGLE_API_KEY"),
            **kwargs,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
            **kwargs,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            **kwargs,
        )

    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            base_url=base_url or "https://openrouter.ai/api/v1",
            **kwargs,
        )

    else:
        raise ValueError(
            f"Unsupported provider '{provider}'."
        )