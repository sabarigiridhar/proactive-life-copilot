import json
import unittest
from unittest.mock import patch

from life_copilot.agent import nodes, provider
from life_copilot.agent.provider import (
    ProviderCallError,
    ProviderFailureKind,
    RetryPolicy,
    call_provider,
    classify_provider_error,
    generate_gemini_content,
)


class HttpError(Exception):
    def __init__(self, status_code, message="provider details"):
        self.status_code = status_code
        super().__init__(message)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class SequenceModel:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.last_kwargs = None

    def generate_content(self, *_args, **_kwargs):
        self.last_kwargs = _kwargs
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


class FakeClient:
    def __init__(self, models):
        self.models = models


ZERO_DELAY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay_seconds=0,
    max_delay_seconds=0,
    jitter_ratio=0,
)


class ProviderReliabilityTests(unittest.TestCase):
    def test_new_genai_client_receives_timeout_and_generation_config(self):
        model = SequenceModel(("ok",))
        config = {"response_mime_type": "application/json"}

        with patch.object(
            provider.genai, "Client", return_value=FakeClient(model)
        ) as client_constructor, patch.object(
            provider.os, "getenv", return_value="test-key"
        ):
            result = generate_gemini_content(
                "Return JSON",
                model_name="test-model",
                generation_config=config,
            )

        self.assertEqual(result, "ok")
        self.assertEqual(client_constructor.call_args.kwargs["api_key"], "test-key")
        self.assertEqual(
            client_constructor.call_args.kwargs["http_options"].timeout,
            provider.PROVIDER_TIMEOUT_MILLISECONDS,
        )
        self.assertEqual(model.last_kwargs["model"], "test-model")
        self.assertEqual(model.last_kwargs["contents"], "Return JSON")
        self.assertEqual(
            model.last_kwargs["config"],
            {
                **config,
                "automatic_function_calling": {"disable": True},
            },
        )

    def test_missing_gemini_key_is_a_permanent_safe_failure(self):
        with patch.object(provider.os, "getenv", return_value=None), patch.object(
            provider.genai, "Client"
        ) as client_constructor:
            with self.assertRaises(ProviderCallError) as caught:
                generate_gemini_content("Hello", model_name="test-model")

        client_constructor.assert_not_called()
        self.assertEqual(
            caught.exception.kind,
            ProviderFailureKind.AUTHENTICATION,
        )
        self.assertEqual(caught.exception.attempts, 1)
        self.assertIn("not configured correctly", str(caught.exception))

    def test_retryable_and_permanent_errors_are_classified(self):
        cases = (
            (HttpError(429), ProviderFailureKind.RATE_LIMIT, True),
            (TimeoutError("secret request"), ProviderFailureKind.TIMEOUT, True),
            (ConnectionError("network"), ProviderFailureKind.CONNECTION, True),
            (HttpError(503), ProviderFailureKind.SERVER, True),
            (HttpError(401), ProviderFailureKind.AUTHENTICATION, False),
            (HttpError(400), ProviderFailureKind.BAD_REQUEST, False),
        )

        for error, kind, retryable in cases:
            with self.subTest(kind=kind):
                info = classify_provider_error(error)
                self.assertEqual(info.kind, kind)
                self.assertEqual(info.retryable, retryable)

    def test_rate_limit_uses_bounded_exponential_backoff(self):
        outcomes = iter((HttpError(429), HttpError(429), "ok"))
        delays = []

        def attempt():
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        result = call_provider(
            attempt,
            provider="test",
            operation="backoff",
            policy=RetryPolicy(
                max_attempts=3,
                base_delay_seconds=1,
                max_delay_seconds=5,
                jitter_ratio=0,
            ),
            sleep=delays.append,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(delays, [1, 2])

    def test_permanent_failure_is_not_retried_or_leaked(self):
        calls = 0

        def attempt():
            nonlocal calls
            calls += 1
            raise HttpError(401, "invalid key: top-secret")

        with self.assertRaises(ProviderCallError) as caught:
            call_provider(
                attempt,
                provider="test",
                operation="auth",
                policy=ZERO_DELAY_POLICY,
            )

        self.assertEqual(calls, 1)
        self.assertNotIn("top-secret", str(caught.exception))
        self.assertIn("not configured correctly", str(caught.exception))

    def test_malformed_json_is_retried_before_a_valid_response(self):
        model = SequenceModel(("{bad json", '{"value": 7}'))

        with patch.object(
            provider.genai, "Client", return_value=FakeClient(model)
        ), patch.object(provider.os, "getenv", return_value="test-key"):
            result = generate_gemini_content(
                "Return JSON",
                model_name="test-model",
                validator=json.loads,
                policy=ZERO_DELAY_POLICY,
            )

        self.assertEqual(result, {"value": 7})
        self.assertEqual(model.calls, 2)

    def test_empty_output_exhausts_retries_with_safe_message(self):
        model = SequenceModel((" ", "", "\n"))

        with patch.object(
            provider.genai, "Client", return_value=FakeClient(model)
        ), patch.object(provider.os, "getenv", return_value="test-key"):
            with self.assertRaises(ProviderCallError) as caught:
                generate_gemini_content(
                    "Return text",
                    model_name="test-model",
                    policy=ZERO_DELAY_POLICY,
                )

        self.assertEqual(caught.exception.kind, ProviderFailureKind.INVALID_OUTPUT)
        self.assertEqual(caught.exception.attempts, 3)
        self.assertIn("invalid response", str(caught.exception))
        self.assertIn("Nothing was saved", str(caught.exception))

    def test_timeout_exhausts_retries(self):
        calls = 0

        def attempt():
            nonlocal calls
            calls += 1
            raise TimeoutError("private prompt")

        with self.assertRaises(ProviderCallError) as caught:
            call_provider(
                attempt,
                provider="test",
                operation="timeout",
                policy=ZERO_DELAY_POLICY,
            )

        self.assertEqual(calls, 3)
        self.assertEqual(caught.exception.kind, ProviderFailureKind.TIMEOUT)
        self.assertNotIn("private prompt", str(caught.exception))

    def test_extraction_failure_returns_no_draft_and_safe_message(self):
        model = SequenceModel(
            (
                HttpError(429, "user secret"),
                HttpError(429, "user secret"),
                HttpError(429, "user secret"),
            )
        )

        with patch.object(
            provider.genai, "Client", return_value=FakeClient(model)
        ), patch.object(
            provider.os, "getenv", return_value="test-key"
        ), patch.object(provider.time, "sleep"):
            result = nodes.extract_data_node(
                {"user_message": "Spent 50 on food", "source": "text"}
            )

        self.assertIsNone(result["draft"])
        self.assertIn("temporarily unavailable", result["ai_response"])
        self.assertIn("Nothing was saved", result["ai_response"])
        self.assertNotIn("user secret", result["ai_response"])


if __name__ == "__main__":
    unittest.main()
