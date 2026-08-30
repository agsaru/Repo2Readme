"""Resolving ``--provider`` / ``--model`` / ``--base-url`` once, for the whole run.

Each of the four LLM call sites used to apply its own default:

    summarize/summary.py            provider or "groq"
    summarize/directory_summary.py  provider or "groq"
    readme/readme_generator.py      provider or "groq"
    readme/reviewer_agent.py        provider or "google"

so a run with no ``--provider`` talked to two vendors, needed two API keys, and
handed the same ``--model`` string to both of them. ``--model llama-3.3-70b``
summarized fine on Groq and then died in review, because Google has never heard
of that model - and "model not found" is (correctly) not retried.

:class:`LLMSettings` is that decision, made once. Every call site is given a
resolved provider, model and base URL, and nothing downstream applies a default
of its own. The reviewer can still be pointed at a different vendor, but only
deliberately, through ``--reviewer-provider``; and when it is, it gets *that*
provider's default model rather than a model name chosen for another vendor.
"""

from __future__ import annotations

from dataclasses import dataclass

from repo2readme.providers import (
    ProviderSpec,
    UnknownProviderError,
    get_provider,
    resolve_base_url,
    resolve_model,
)

# The provider used when nothing is specified. This is the historical default
# of three of the four call sites, and the one the README documents.
DEFAULT_PROVIDER = "groq"


@dataclass(frozen=True)
class LLMSettings:
    """A fully resolved provider/model/base-url triple.

    ``provider`` is always the canonical registry name, so ``--provider gemini``
    and ``--provider google`` produce identical settings - and therefore
    identical cache keys.
    """

    provider: str
    model: str
    base_url: str | None
    label: str
    env_var: str | None

    @property
    def requires_api_key(self) -> bool:
        return self.env_var is not None

    @property
    def spec(self) -> ProviderSpec:
        return get_provider(self.provider)

    def as_cache_config(self) -> dict:
        """The identity the summary cache should key on.

        The cache used to hash the raw CLI values, so ``--provider groq`` and no
        flags at all - the same run, resolving to the same provider and the same
        model - produced different hashes and invalidated each other.
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
        }

    def describe(self) -> str:
        """One line naming what will actually be called."""
        text = f"{self.label} ({self.model})"
        if self.base_url:
            text += f" via {self.base_url}"
        return text

    def replace(self, **changes) -> LLMSettings:
        """A copy with individual fields overridden, re-resolved consistently."""
        return resolve_settings(
            provider=changes.get("provider", self.provider),
            model=changes.get("model", self.model),
            base_url=changes.get("base_url", self.base_url),
        )


def resolve_settings(
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LLMSettings:
    """
    Turn the raw CLI values into settings every call site can share.

    Raises
    ------
    UnknownProviderError
        If ``provider`` is not in the registry. Callers are expected to do this
        before any expensive work, so a typo costs a second rather than a clone
        and an API key prompt.
    """
    spec = get_provider(provider or DEFAULT_PROVIDER)

    return LLMSettings(
        provider=spec.name,
        model=resolve_model(spec.name, model),
        base_url=resolve_base_url(spec.name, base_url),
        label=spec.label,
        env_var=spec.env_var,
    )


def resolve_reviewer_settings(
    main: LLMSettings,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LLMSettings:
    """
    Settings for the README reviewer.

    The reviewer follows the main settings unless it is explicitly pointed
    somewhere else. The rule that matters is the one about the model: a model
    name belongs to the provider it was given for. When the reviewer runs on a
    *different* provider and no reviewer model was named, it uses that
    provider's default model rather than inheriting a name that means nothing
    there - which is exactly how ``--model`` used to break the review step.
    """
    if not provider:
        if model or base_url:
            return resolve_settings(
                provider=main.provider,
                model=model or main.model,
                base_url=base_url or main.base_url,
            )
        return main

    spec = get_provider(provider)

    if spec.name == main.provider:
        # Same vendor: inheriting the model is the right thing to do.
        return resolve_settings(
            provider=spec.name,
            model=model or main.model,
            base_url=base_url or main.base_url,
        )

    # A different vendor: only what was said about the reviewer applies.
    return resolve_settings(provider=spec.name, model=model, base_url=base_url)


def validate_providers(*names: str | None) -> None:
    """
    Fail on an unknown provider name before any work is done.

    ``--provider grok`` (a typo for ``groq``) used to load the whole
    repository, prompt for an API key and only then raise.

    Raises
    ------
    UnknownProviderError
    """
    for name in names:
        if name:
            get_provider(name)


def required_api_keys(*settings: LLMSettings | None) -> list[LLMSettings]:
    """The distinct providers in ``settings`` that need an API key.

    Deduplicated by provider, so a run that uses one vendor for everything asks
    for one key - not the two that were unconditionally demanded when no
    ``--provider`` was given.
    """
    seen: set[str] = set()
    needed: list[LLMSettings] = []

    for setting in settings:
        if setting is None or not setting.requires_api_key:
            continue
        if setting.provider in seen:
            continue
        seen.add(setting.provider)
        needed.append(setting)

    return needed


__all__ = [
    "DEFAULT_PROVIDER",
    "LLMSettings",
    "UnknownProviderError",
    "required_api_keys",
    "resolve_reviewer_settings",
    "resolve_settings",
    "validate_providers",
]
