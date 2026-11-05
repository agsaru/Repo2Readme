import pytest
from langchain_core.exceptions import (
    OutputParserException as RealOutputParserException,
)

from repo2readme.utils.retry import (
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_RETRIES,
    ENV_BASE_DELAY,
    ENV_MAX_RETRIES,
    RetryConfig,
    call_with_retry,
    compute_delay,
    is_retryable,
    retry_after_seconds,
    status_code_of,
)


class FakeResponse:
    def __init__(self, status_code=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


class ProviderError(Exception):
    """Stands in for the SDK exceptions, which carry a response object."""

    def __init__(self, message, status_code=None, headers=None):
        super().__init__(message)
        self.response = FakeResponse(status_code, headers)


class OutputParserException(Exception):
    """Same name as LangChain's, which is what the classifier looks at."""


def _no_sleep(_seconds):
    return None


def _config(**kwargs):
    defaults = {"max_retries": 2, "base_delay": 0.0, "jitter": 0.0}
    defaults.update(kwargs)
    return RetryConfig(**defaults)


class TestStatusExtraction:
    def test_reads_status_code_attribute(self):
        exc = type("E", (Exception,), {"status_code": 429})()
        assert status_code_of(exc) == 429

    def test_reads_status_from_response(self):
        assert status_code_of(ProviderError("boom", status_code=503)) == 503

    def test_parses_status_out_of_the_message(self):
        exc = Exception("Error code: 429 - {'error': {'message': 'Rate limit'}}")
        assert status_code_of(exc) == 429

    def test_returns_none_when_there_is_no_status(self):
        assert status_code_of(Exception("something went wrong")) is None

    def test_ignores_out_of_range_values(self):
        exc = type("E", (Exception,), {"code": 99})()
        assert status_code_of(exc) is None


class TestClassification:
    @pytest.mark.parametrize("status", [408, 409, 425, 429, 500, 502, 503, 504])
    def test_transient_statuses_are_retryable(self, status):
        assert is_retryable(ProviderError("boom", status_code=status))

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 413, 422])
    def test_client_errors_are_not_retryable(self, status):
        assert not is_retryable(ProviderError("boom", status_code=status))

    def test_builtin_network_errors_are_retryable(self):
        assert is_retryable(TimeoutError("read timed out"))
        assert is_retryable(ConnectionError("connection reset by peer"))

    @pytest.mark.parametrize(
        "message",
        [
            "Rate limit reached for model",
            "Too Many Requests",
            "The server is overloaded, please try again",
            "Service Unavailable",
            "Bad gateway",
            "Connection aborted",
        ],
    )
    def test_transient_messages_are_retryable(self, message):
        assert is_retryable(Exception(message))

    @pytest.mark.parametrize(
        "message",
        [
            "Invalid API key provided",
            "Authentication failed",
            "Unauthorized",
            "Unsupported provider 'vertex'",
            "This model's maximum context length is 8192 tokens",
        ],
    )
    def test_permanent_messages_are_not_retryable(self, message):
        assert not is_retryable(Exception(message))

    def test_configuration_errors_are_never_retried(self):
        assert not is_retryable(ValueError("Unsupported provider: nope"))
        assert not is_retryable(ImportError("No module named 'langchain_groq'"))
        assert not is_retryable(TypeError("bad argument"))

    def test_parser_failures_are_retryable(self):
        assert is_retryable(OutputParserException("Invalid json output: ```json"))

    def test_the_real_langchain_parser_exception_is_retryable(self):
        # The stub above does not inherit from ValueError; the real class does,
        # which is what used to make this classification come out wrong.
        assert is_retryable(RealOutputParserException("Invalid json output: {"))

    def test_unknown_errors_are_not_retried(self):
        # Better to fail fast than to burn three attempts on a real bug.
        assert not is_retryable(Exception("something unusual happened"))

    def test_auth_wins_over_a_retryable_looking_status(self):
        exc = ProviderError("Invalid API key", status_code=401)
        assert not is_retryable(exc)


class TestRetryAfter:
    def test_reads_the_retry_after_header(self):
        exc = ProviderError("slow down", headers={"retry-after": "7"})
        assert retry_after_seconds(exc) == 7.0

    def test_header_lookup_is_case_insensitive_across_spellings(self):
        exc = ProviderError("slow down", headers={"Retry-After": "3.5"})
        assert retry_after_seconds(exc) == 3.5

    def test_parses_the_hint_groq_puts_in_the_message(self):
        exc = Exception("Rate limit reached. Please try again in 6.7s")
        assert retry_after_seconds(exc) == pytest.approx(6.7)

    def test_understands_millisecond_and_minute_hints(self):
        assert retry_after_seconds(Exception("try again in 500ms")) == 0.5
        assert retry_after_seconds(Exception("try again in 2m")) == 120.0

    def test_returns_none_without_a_hint(self):
        assert retry_after_seconds(Exception("boom")) is None

    def test_ignores_a_non_numeric_header(self):
        exc = ProviderError("boom", headers={"retry-after": "Wed, 21 Oct 2026"})
        assert retry_after_seconds(exc) is None


class TestDelay:
    def test_backoff_is_exponential(self):
        config = RetryConfig(base_delay=1.0, jitter=0.0, max_delay=100)
        assert compute_delay(0, config) == 1.0
        assert compute_delay(1, config) == 2.0
        assert compute_delay(2, config) == 4.0

    def test_delay_is_capped(self):
        config = RetryConfig(base_delay=10.0, jitter=0.0, max_delay=15.0)
        assert compute_delay(5, config) == 15.0

    def test_jitter_stays_within_bounds(self):
        config = RetryConfig(base_delay=2.0, jitter=0.25, max_delay=100)
        assert compute_delay(0, config, rng=lambda: 0.0) == 2.0
        assert compute_delay(0, config, rng=lambda: 1.0) == 2.5

    def test_provider_hint_overrides_the_computed_backoff(self):
        config = RetryConfig(base_delay=1.0, jitter=0.0, max_delay=100)
        assert compute_delay(0, config, retry_after=9.0) == 9.0

    def test_provider_hint_is_still_capped(self):
        config = RetryConfig(base_delay=1.0, jitter=0.0, max_delay=5.0)
        assert compute_delay(0, config, retry_after=600) == 5.0


class TestConfigFromEnv:
    def test_defaults_when_unset(self):
        config = RetryConfig.from_env({})
        assert config.max_retries == DEFAULT_MAX_RETRIES
        assert config.base_delay == DEFAULT_BASE_DELAY

    def test_values_are_read_from_the_environment(self):
        config = RetryConfig.from_env(
            {ENV_MAX_RETRIES: "5", ENV_BASE_DELAY: "0.5"}
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5

    def test_zero_retries_is_allowed_and_means_one_attempt(self):
        config = RetryConfig.from_env({ENV_MAX_RETRIES: "0"})
        assert config.max_retries == 0
        assert config.max_attempts == 1

    @pytest.mark.parametrize("value", ["abc", "-1", ""])
    def test_unusable_values_fall_back_to_the_default(self, value):
        config = RetryConfig.from_env({ENV_MAX_RETRIES: value})
        assert config.max_retries == DEFAULT_MAX_RETRIES

    def test_reads_the_real_environment_by_default(self, monkeypatch):
        monkeypatch.setenv(ENV_MAX_RETRIES, "4")
        assert RetryConfig.from_env().max_retries == 4


class TestCallWithRetry:
    def test_returns_immediately_on_success(self):
        calls = []

        def func():
            calls.append(1)
            return "ok"

        assert call_with_retry(func, config=_config(), sleep=_no_sleep) == "ok"
        assert len(calls) == 1

    def test_retries_a_transient_failure_then_succeeds(self):
        calls = []

        def func():
            calls.append(1)
            if len(calls) < 3:
                raise ProviderError("rate limit", status_code=429)
            return "ok"

        assert call_with_retry(func, config=_config(), sleep=_no_sleep) == "ok"
        assert len(calls) == 3

    def test_reraises_after_exhausting_attempts(self):
        calls = []

        def func():
            calls.append(1)
            raise ProviderError("rate limit", status_code=429)

        with pytest.raises(ProviderError):
            call_with_retry(func, config=_config(max_retries=2), sleep=_no_sleep)

        assert len(calls) == 3

    def test_permanent_failures_are_not_retried(self):
        calls = []

        def func():
            calls.append(1)
            raise ProviderError("Invalid API key", status_code=401)

        with pytest.raises(ProviderError):
            call_with_retry(func, config=_config(), sleep=_no_sleep)

        assert len(calls) == 1

    def test_zero_retries_makes_exactly_one_attempt(self):
        calls = []

        def func():
            calls.append(1)
            raise ProviderError("rate limit", status_code=429)

        with pytest.raises(ProviderError):
            call_with_retry(func, config=_config(max_retries=0), sleep=_no_sleep)

        assert len(calls) == 1

    def test_sleeps_between_attempts_with_growing_delays(self):
        slept = []
        calls = []

        def func():
            calls.append(1)
            raise ProviderError("rate limit", status_code=429)

        config = RetryConfig(max_retries=2, base_delay=1.0, jitter=0.0, max_delay=60)
        with pytest.raises(ProviderError):
            call_with_retry(func, config=config, sleep=slept.append)

        assert slept == [1.0, 2.0]

    def test_honours_the_provider_retry_after_hint(self):
        slept = []
        state = {"calls": 0}

        def func():
            state["calls"] += 1
            if state["calls"] == 1:
                raise ProviderError(
                    "rate limit", status_code=429, headers={"retry-after": "4"}
                )
            return "ok"

        config = RetryConfig(max_retries=2, base_delay=1.0, jitter=0.0, max_delay=60)
        assert call_with_retry(func, config=config, sleep=slept.append) == "ok"
        assert slept == [4.0]

    def test_does_not_sleep_after_the_final_attempt(self):
        slept = []

        def func():
            raise ProviderError("rate limit", status_code=429)

        with pytest.raises(ProviderError):
            call_with_retry(func, config=_config(max_retries=1), sleep=slept.append)

        assert len(slept) == 1

    def test_custom_predicate_is_used(self):
        calls = []

        def func():
            calls.append(1)
            raise RuntimeError("weird")

        with pytest.raises(RuntimeError):
            call_with_retry(
                func,
                config=_config(max_retries=2),
                retryable=lambda exc: True,
                sleep=_no_sleep,
            )

        assert len(calls) == 3

    def test_logs_each_retry(self, caplog):
        import logging

        state = {"calls": 0}

        def func():
            state["calls"] += 1
            if state["calls"] == 1:
                raise ProviderError("rate limit", status_code=429)
            return "ok"

        with caplog.at_level(logging.DEBUG, logger="repo2readme.utils.retry"):
            call_with_retry(
                func, config=_config(), description="summary for a.py", sleep=_no_sleep
            )

        assert "summary for a.py" in caplog.text
        assert "attempt 1/3" in caplog.text


class TestCallSites:
    def test_summarize_file_retries_and_returns_the_summary(self, monkeypatch):
        from repo2readme.summarize import summary as summary_module

        state = {"calls": 0}

        class FakeChain:
            def invoke(self, _payload):
                state["calls"] += 1
                if state["calls"] < 3:
                    raise ProviderError("rate limit", status_code=429)
                return {"file_path": "a.py", "description": "ok"}

        monkeypatch.setattr(
            summary_module, "create_summarizer", lambda *a, **k: FakeChain()
        )
        monkeypatch.setenv(ENV_BASE_DELAY, "0")

        result = summary_module.summarize_file("a.py", "python", "x = 1")

        assert result == {"file_path": "a.py", "description": "ok"}
        assert state["calls"] == 3

    def test_summarize_file_still_returns_an_error_dict_when_retries_run_out(
        self, monkeypatch
    ):
        from repo2readme.summarize import summary as summary_module

        state = {"calls": 0}

        class FakeChain:
            def invoke(self, _payload):
                state["calls"] += 1
                raise ProviderError("rate limit", status_code=429)

        monkeypatch.setattr(
            summary_module, "create_summarizer", lambda *a, **k: FakeChain()
        )
        monkeypatch.setenv(ENV_MAX_RETRIES, "1")
        monkeypatch.setenv(ENV_BASE_DELAY, "0")

        result = summary_module.summarize_file("a.py", "python", "x = 1")

        assert "error" in result
        assert state["calls"] == 2

    def test_permanent_error_is_not_retried_by_the_summarizer(self, monkeypatch):
        from repo2readme.summarize import summary as summary_module

        state = {"calls": 0}

        class FakeChain:
            def invoke(self, _payload):
                state["calls"] += 1
                raise ProviderError("Invalid API key", status_code=401)

        monkeypatch.setattr(
            summary_module, "create_summarizer", lambda *a, **k: FakeChain()
        )
        monkeypatch.setenv(ENV_BASE_DELAY, "0")

        result = summary_module.summarize_file("a.py", "python", "x = 1")

        assert "error" in result
        assert state["calls"] == 1



@pytest.mark.parametrize("raw", ["nan", "inf", "-inf"])
def test_non_finite_retry_delays_are_ignored(raw):
    config = RetryConfig.from_env({ENV_BASE_DELAY: raw})

    assert config.base_delay == DEFAULT_BASE_DELAY
