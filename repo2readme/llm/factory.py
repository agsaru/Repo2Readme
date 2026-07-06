import os

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

# ------------------------------------------------------------
# Default configuration
# (Preserves existing behaviour)
# ------------------------------------------------------------

DEFAULT_CONFIG = {
    "summarizer": {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "temperature": 0.2,
    },
    "generator": {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "temperature": 0.2,
    },
    "reviewer": {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "temperature": 0.2,
    },
}

# ------------------------------------------------------------
# Runtime overrides from CLI
# ------------------------------------------------------------

_RUNTIME_CONFIG = {
    "provider": None,
    "model": None,
    "base_url": None,
}


def configure_llm(provider=None, model=None, base_url=None):
    """
    Configure runtime overrides supplied from the CLI.
    """

    _RUNTIME_CONFIG["provider"] = provider
    _RUNTIME_CONFIG["model"] = model
    _RUNTIME_CONFIG["base_url"] = base_url


def create_llm(
    stage: str,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
):
    """
    Creates a chat model for the requested pipeline stage.
    """

    if stage not in DEFAULT_CONFIG:
        raise ValueError(f"Unknown pipeline stage: {stage}")

    config = DEFAULT_CONFIG[stage]

    provider = (
        provider
        or _RUNTIME_CONFIG["provider"]
        or config["provider"]
    )

    model = (
        model
        or _RUNTIME_CONFIG["model"]
        or config["model"]
    )

    temperature = (
        temperature
        if temperature is not None
        else config["temperature"]
    )

    provider = provider.lower()

    if provider == "groq":
        return ChatGroq(
            model=model,
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=temperature,
        )

    if provider in ("google", "gemini"):
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=temperature,
        )

    raise ValueError(f"Unsupported provider: {provider}")


def get_llm(stage: str):
    """
    Returns the configured LLM for a pipeline stage.
    """

    return create_llm(stage)