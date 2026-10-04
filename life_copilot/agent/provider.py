"""Provider calls with classified failures, bounded retries, and safe messages."""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from google import genai
from google.genai import types
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

LOGGER = logging.getLogger(__name__)
PROVIDER_TIMEOUT_SECONDS = 30.0
PROVIDER_TIMEOUT_MILLISECONDS = int(PROVIDER_TIMEOUT_SECONDS * 1000)
T = TypeVar("T")


class ProviderFailureKind(str, Enum):
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    SERVER = "server"
    AUTHENTICATION = "authentication"
    BAD_REQUEST = "bad_request"
    INVALID_OUTPUT = "invalid_output"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderErrorInfo:
    kind: ProviderFailureKind
    retryable: bool


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 4.0
    jitter_ratio: float = 0.2

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("Retry delays cannot be negative.")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1.")


DEFAULT_RETRY_POLICY = RetryPolicy()


class ProviderOutputError(ValueError):
    """Raised when a provider response is empty, malformed, or out of contract."""


class ProviderConfigurationError(RuntimeError):
    """Raised when a required provider setting is missing."""


class ProviderCallError(RuntimeError):
    """Sanitized final provider failure suitable for application boundaries."""

    def __init__(
        self,
        provider: str,
        operation: str,
        info: ProviderErrorInfo,
        attempts: int,
    ):
        self.provider = provider
        self.operation = operation
        self.kind = info.kind
        self.retryable = info.retryable
        self.attempts = attempts
        super().__init__(provider_user_message(self))


def _status_code(exc: Exception) -> int | None:
    direct = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    response = getattr(exc, "response", None)
    value = direct or getattr(response, "status_code", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def classify_provider_error(exc: Exception) -> ProviderErrorInfo:
    """Classify SDK-independent HTTP and transport failures."""
    if isinstance(exc, ProviderOutputError):
        return ProviderErrorInfo(ProviderFailureKind.INVALID_OUTPUT, True)
    if isinstance(exc, ProviderConfigurationError):
        return ProviderErrorInfo(ProviderFailureKind.AUTHENTICATION, False)

    status = _status_code(exc)
    name = type(exc).__name__.casefold()
    message = str(exc).casefold()
    combined = f"{name} {message}"
    if status == 429 or any(
        token in combined for token in ("ratelimit", "rate limit", "resourceexhausted")
    ):
        return ProviderErrorInfo(ProviderFailureKind.RATE_LIMIT, True)
    if status in {408, 504} or isinstance(exc, TimeoutError) or any(
        token in combined for token in ("timeout", "timed out", "deadlineexceeded")
    ):
        return ProviderErrorInfo(ProviderFailureKind.TIMEOUT, True)
    if isinstance(exc, ConnectionError) or any(
        token in combined for token in ("connectionerror", "apiconnection", "network")
    ):
        return ProviderErrorInfo(ProviderFailureKind.CONNECTION, True)
    if (status is not None and 500 <= status <= 599) or any(
        token in combined
        for token in ("serviceunavailable", "internalservererror", "servererror")
    ):
        return ProviderErrorInfo(ProviderFailureKind.SERVER, True)
    if status in {401, 403} or any(
        token in combined
        for token in (
            "authenticationerror",
            "unauthenticated",
            "permissiondenied",
            "invalid api key",
        )
    ):
        return ProviderErrorInfo(ProviderFailureKind.AUTHENTICATION, False)
    if status in {400, 404, 413, 422} or any(
        token in combined for token in ("badrequest", "invalidargument")
    ):
        return ProviderErrorInfo(ProviderFailureKind.BAD_REQUEST, False)
    return ProviderErrorInfo(ProviderFailureKind.UNKNOWN, False)


def provider_user_message(error: ProviderCallError) -> str:
    """Return a fixed message that never exposes SDK details or private input."""
    if error.kind == ProviderFailureKind.AUTHENTICATION:
        return (
            "The AI service is not configured correctly. Nothing was saved. "
            "Please check the API key and try again."
        )
    if error.kind == ProviderFailureKind.INVALID_OUTPUT:
        return (
            "The AI service returned an invalid response after several attempts. "
            "Nothing was saved. Please try again."
        )
    if error.retryable:
        return (
            "The AI service is temporarily unavailable after several attempts. "
            "Nothing was saved. Please try again shortly."
        )
    return (
        "The AI service could not process that request. Nothing was saved. "
        "Please revise the input or try again."
    )


def call_provider(
    call: Callable[[], Any],
    *,
    provider: str,
    operation: str,
    validator: Callable[[Any], T] | None = None,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    sleep: Callable[[float], None] | None = None,
    random_value: Callable[[], float] | None = None,
) -> T | Any:
    """Execute one side-effect-free provider call with exponential backoff."""
    sleep_function = sleep or time.sleep
    random_function = random_value or random.random
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = call()
            return validator(response) if validator else response
        except ProviderCallError:
            raise
        except Exception as exc:
            info = classify_provider_error(exc)
            LOGGER.warning(
                "Provider call failed provider=%s operation=%s kind=%s attempt=%s",
                provider,
                operation,
                info.kind.value,
                attempt,
            )
            if not info.retryable or attempt == policy.max_attempts:
                raise ProviderCallError(provider, operation, info, attempt) from exc
            base_delay = min(
                policy.max_delay_seconds,
                policy.base_delay_seconds * (2 ** (attempt - 1)),
            )
            jitter = base_delay * policy.jitter_ratio * random_function()
            sleep_function(base_delay + jitter)
    raise AssertionError("Provider retry loop exited unexpectedly.")


def require_text(response: Any, *, max_length: int = 50000) -> str:
    """Extract bounded, non-empty text from a provider response."""
    try:
        text = response if isinstance(response, str) else response.text
    except Exception as exc:
        raise ProviderOutputError("Provider response did not contain text.") from exc
    if not isinstance(text, str) or not text.strip():
        raise ProviderOutputError("Provider response text was empty.")
    cleaned = text.strip()
    if len(cleaned) > max_length:
        raise ProviderOutputError("Provider response exceeded the allowed length.")
    return cleaned


def generate_gemini_content(
    prompt,
    *,
    model_name: str,
    generation_config: dict | None = None,
    validator: Callable[[str], T] | None = None,
    operation: str = "text_generation",
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
) -> T | str:
    """Generate Gemini content and validate it inside the retry boundary."""

    def invoke():
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ProviderConfigurationError("GEMINI_API_KEY is missing.")
        config = dict(generation_config or {})
        config["automatic_function_calling"] = {"disable": True}
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=PROVIDER_TIMEOUT_MILLISECONDS,
            ),
        )
        return client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

    def validate(response):
        text = require_text(response)
        if validator is None:
            return text
        try:
            return validator(text)
        except ProviderOutputError:
            raise
        except Exception as exc:
            raise ProviderOutputError("Provider output failed validation.") from exc

    return call_provider(
        invoke,
        provider="gemini",
        operation=operation,
        validator=validate,
        policy=policy,
    )


def transcribe_groq_audio(
    client=None,
    *,
    file,
    model_name: str = "whisper-large-v3",
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
) -> str:
    """Transcribe audio through the same classified retry boundary."""
    def invoke():
        active_client = client
        if active_client is None:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ProviderConfigurationError("GROQ_API_KEY is missing.")
            active_client = Groq(api_key=api_key)
        return active_client.audio.transcriptions.create(
            file=file,
            model=model_name,
            timeout=PROVIDER_TIMEOUT_SECONDS,
        )

    return call_provider(
        invoke,
        provider="groq",
        operation="audio_transcription",
        validator=lambda response: require_text(response, max_length=20000),
        policy=policy,
    )
