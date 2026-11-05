"""Retry helper for transient LLM failures.

Every LLM call in the project was a single attempt, so one 429 during a
parallel run permanently lost that file's summary. This module adds a small,
dependency-free retry with exponential backoff and jitter.

The important part is the classification: rate limits, timeouts and transient
server errors are worth retrying, while a bad API key or an unsupported
provider is not - retrying those only makes the failure slower.

A response the output parser could not read is also worth retrying. The chains
sample the model, so the next attempt produces different text, and a truncated
object or a stray code fence usually parses on the second ask.
"""

from __future__ import annotations

import logging
import math
import os
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 2
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0
DEFAULT_JITTER = 0.25

ENV_MAX_RETRIES = "REPO2README_MAX_RETRIES"
ENV_BASE_DELAY = "REPO2README_RETRY_BASE_DELAY"

# Statuses worth another attempt: rate limiting, request timeout and the
# transient 5xx family.
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

# Statuses that will never succeed on a retry with the same input.
NON_RETRYABLE_STATUS_CODES = frozenset({400, 401, 403, 404, 413, 422})

RETRYABLE_MESSAGE_PATTERNS = (
    "rate limit",
    "rate_limit",
    "too many requests",
    "timeout",
    "timed out",
    "connection reset",
    "connection aborted",
    "connection error",
    "temporarily unavailable",
    "service unavailable",
    "bad gateway",
    "overloaded",
    "try again",
)

NON_RETRYABLE_MESSAGE_PATTERNS = (
    "invalid api key",
    "incorrect api key",
    "api key not found",
    "authentication",
    "unauthorized",
    "permission denied",
    "unsupported provider",
    "context length",
    "maximum context",
    "model not found",
    "does not exist",
)

# Exception classes raised when the model's answer could not be parsed. Matched
# against every class name in the exception's MRO rather than just its own name:
# the provider integrations subclass these with names of their own, and
# LangChain's OutputParserException is itself a ValueError, which the
# programming-error rejection below would otherwise swallow.
PARSER_EXCEPTION_MARKERS = (
    "outputparserexception",
    "outputparsererror",
    "parsererror",
    "parseexception",
    "validationerror",
    "jsondecodeerror",
)

_STATUS_IN_MESSAGE = re.compile(r"\berror code:\s*(\d{3})\b", re.IGNORECASE)
_RETRY_AFTER_IN_MESSAGE = re.compile(
    r"try again in\s+(\d+(?:\.\d+)?)\s*(ms|s|m)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class RetryConfig:
    """How hard to try. ``max_retries=0`` restores single-attempt behaviour."""

    max_retries: int = DEFAULT_MAX_RETRIES
    base_delay: float = DEFAULT_BASE_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    jitter: float = DEFAULT_JITTER

    @property
    def max_attempts(self) -> int:
        return self.max_retries + 1

    @classmethod
    def from_env(cls, env: dict | None = None) -> RetryConfig:
        """Build a config from the environment, ignoring unusable values."""
        source = os.environ if env is None else env

        return cls(
            max_retries=_read_int(
                source, ENV_MAX_RETRIES, DEFAULT_MAX_RETRIES, minimum=0
            ),
            base_delay=_read_float(
                source, ENV_BASE_DELAY, DEFAULT_BASE_DELAY, minimum=0.0
            ),
        )


def _read_int(source, name: str, default: int, minimum: int) -> int:
    raw = source.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        logger.warning("Ignoring %s=%r: not an integer", name, raw)
        return default
    if value < minimum:
        logger.warning("Ignoring %s=%r: must be >= %d", name, raw, minimum)
        return default
    return value


def _read_float(source, name: str, default: float, minimum: float) -> float:
    raw = source.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        logger.warning("Ignoring %s=%r: not a number", name, raw)
        return default
    if not math.isfinite(value) or value < minimum:
        logger.warning(
            "Ignoring %s=%r: must be finite and >= %s", name, raw, minimum
        )
        return default
    return value


def status_code_of(exc: BaseException) -> int | None:
    """Best-effort HTTP status extraction across the provider SDKs."""
    for attribute in ("status_code", "http_status", "code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value

    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value

    match = _STATUS_IN_MESSAGE.search(str(exc))
    if match:
        return int(match.group(1))

    return None


def exception_class_names(exc: BaseException) -> tuple[str, ...]:
    """Lowercased names of ``exc``'s class and every class it inherits from."""
    return tuple(cls.__name__.lower() for cls in type(exc).__mro__)


def is_parse_error(exc: BaseException) -> bool:
    """Whether ``exc`` means the model's answer could not be parsed.

    Covers the parser exceptions raised by the JSON and Pydantic parsers on the
    summarization and review chains, including provider-specific subclasses.
    """
    names = exception_class_names(exc)
    return any(
        marker in name for name in names for marker in PARSER_EXCEPTION_MARKERS
    )


def is_retryable(exc: BaseException) -> bool:
    """Whether another attempt could plausibly succeed."""
    # Checked before the programming-error rejection below, because
    # OutputParserException subclasses ValueError and would never reach a later
    # branch. The message is not consulted either: it embeds the model's own
    # output, so scanning it for phrases like "authentication" reads the answer
    # as if it were an error report.
    if is_parse_error(exc):
        return True

    # Programming and configuration errors: never worth a retry.
    if isinstance(exc, (TypeError, KeyError, AttributeError, ImportError,
                        NotImplementedError, ValueError)):
        return False

    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True

    status = status_code_of(exc)
    if status is not None:
        if status in NON_RETRYABLE_STATUS_CODES:
            return False
        if status in RETRYABLE_STATUS_CODES:
            return True

    message = str(exc).lower()

    if any(pattern in message for pattern in NON_RETRYABLE_MESSAGE_PATTERNS):
        return False

    return any(pattern in message for pattern in RETRYABLE_MESSAGE_PATTERNS)


def retry_after_seconds(exc: BaseException) -> float | None:
    """Read the provider's own backoff hint, if it gave one."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        for key in ("retry-after", "Retry-After"):
            try:
                raw = headers.get(key)
            except AttributeError:
                raw = None
            if raw is not None:
                try:
                    value = float(str(raw).strip())
                except ValueError:
                    continue
                if value >= 0:
                    return value

    match = _RETRY_AFTER_IN_MESSAGE.search(str(exc))
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit == "ms":
            return value / 1000
        if unit == "m":
            return value * 60
        return value

    return None


def compute_delay(
    attempt: int,
    config: RetryConfig,
    retry_after: float | None = None,
    rng: Callable[[], float] = random.random,
) -> float:
    """Delay before the next attempt (``attempt`` is 0-based).

    A provider-supplied ``retry_after`` wins over the computed backoff, because
    guessing shorter than the server asked for just earns another 429.
    """
    if retry_after is not None:
        return min(max(retry_after, 0.0), config.max_delay)

    delay = min(config.base_delay * (2 ** attempt), config.max_delay)
    if config.jitter:
        delay += delay * config.jitter * rng()
    return min(delay, config.max_delay)


def call_with_retry(
    func: Callable[[], Any],
    *,
    config: RetryConfig | None = None,
    description: str = "LLM call",
    retryable: Callable[[BaseException], bool] = is_retryable,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> Any:
    """Call ``func`` retrying transient failures.

    The last exception is re-raised once the attempts are exhausted, so callers
    keep their existing error handling.
    """
    config = config or RetryConfig.from_env()
    attempts = max(1, config.max_attempts)
    last_exc: BaseException | None = None

    for attempt in range(attempts):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 - re-raised below
            last_exc = exc
            is_last_attempt = attempt == attempts - 1

            if is_last_attempt or not retryable(exc):
                raise

            delay = compute_delay(
                attempt, config, retry_after=retry_after_seconds(exc), rng=rng
            )
            logger.debug(
                "%s failed (attempt %d/%d): %s. Retrying in %.2fs",
                description,
                attempt + 1,
                attempts,
                exc,
                delay,
            )
            sleep(delay)

    # Only reachable if attempts is 0, which max(1, ...) prevents.
    raise last_exc  # pragma: no cover
