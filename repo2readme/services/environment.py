import os

from repo2readme.config import get_api_key
from repo2readme.llm.settings import LLMSettings, required_api_keys, resolve_settings


def setup_api_keys(*targets) -> None:
    """Configure API keys and export them as environment variables.

    Each target is either a provider name or an :class:`LLMSettings`. Providers
    are deduplicated, so a run that uses one vendor for everything asks for
    exactly one key. Providers that do not authenticate (a local Ollama server,
    for example) are accepted and simply skip the export.

    With no target, the project default provider is used. This used to export
    both ``GROQ_API_KEY`` and ``GOOGLE_API_KEY``, because the summarizer
    defaulted to Groq and the reviewer to Google: a run without ``--provider``
    genuinely needed two keys from two vendors, and a user holding one of them
    discovered that from a stack trace half way through.

    Raises
    ------
    UnknownProviderError
        If a provider name is not in the registry. The message lists every
        supported provider.
    """
    settings = [
        target if isinstance(target, LLMSettings) else resolve_settings(target)
        for target in targets
    ] or [resolve_settings()]

    for needed in required_api_keys(*settings):
        api_key = get_api_key(needed.provider)
        if api_key:
            os.environ[needed.env_var] = api_key
