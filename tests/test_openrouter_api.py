import unittest
from types import SimpleNamespace
from unittest import mock

import httpx
import openrouter.errors
from openrouter.types import UNSET

from llm_workbench.errors import ModelResponseError, OpenRouterRequestError
from llm_workbench.llm import openrouter_api


def sdk_error(error_class: type[openrouter.errors.OpenRouterError], headers: dict | None = None) -> Exception:
    # the SDK's error classes need generated response models, the base initializer only needs the http response
    error = error_class.__new__(error_class)
    openrouter.errors.OpenRouterError.__init__(error, "error", httpx.Response(500, headers=headers))
    return error


@mock.patch.object(openrouter_api.time, "sleep")
class SafeRunTests(unittest.TestCase):
    def test_returns_result_without_retrying(self, sleep) -> None:
        function = mock.Mock(return_value="result")

        self.assertEqual(openrouter_api._safe_run(function, model="x"), "result")
        function.assert_called_once_with(model="x")
        sleep.assert_not_called()

    def test_retries_temporary_errors(self, sleep) -> None:
        function = mock.Mock(side_effect=[httpx.ConnectError("offline"), "result"])

        self.assertEqual(openrouter_api._safe_run(function), "result")
        self.assertEqual(function.call_count, 2)
        sleep.assert_called_once_with(openrouter_api.RETRY_DELAY_S)

    def test_raises_after_last_retry(self, sleep) -> None:
        function = mock.Mock(side_effect=httpx.ConnectError("offline"))

        with self.assertRaises(OpenRouterRequestError) as context:
            openrouter_api._safe_run(function, max_retries=2)

        self.assertEqual(function.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(context.exception.kind, "network")
        self.assertIsInstance(context.exception.original_error, httpx.ConnectError)

    def test_does_not_retry_permanent_errors(self, sleep) -> None:
        function = mock.Mock(side_effect=sdk_error(openrouter.errors.UnauthorizedResponseError))

        with self.assertRaises(OpenRouterRequestError) as context:
            openrouter_api._safe_run(function)

        function.assert_called_once()
        sleep.assert_not_called()
        self.assertEqual(context.exception.kind, "auth")

    def test_rate_limit_waits_for_retry_after_header(self, sleep) -> None:
        error = sdk_error(openrouter.errors.TooManyRequestsResponseError, headers={"retry-after": "7"})
        function = mock.Mock(side_effect=[error, "result"])

        self.assertEqual(openrouter_api._safe_run(function), "result")
        sleep.assert_called_once_with(7.0)

    def test_rate_limit_without_valid_header_uses_default_delay(self, sleep) -> None:
        for headers in (
            None,
            {"retry-after": "soon"},
            {"retry-after": "-1"},
            {"retry-after": "nan"},
            {"retry-after": "inf"},
        ):
            sleep.reset_mock()
            error = sdk_error(openrouter.errors.TooManyRequestsResponseError, headers=headers)
            function = mock.Mock(side_effect=[error, "result"])

            with self.subTest(headers=headers):
                self.assertEqual(openrouter_api._safe_run(function), "result")
                sleep.assert_called_once_with(openrouter_api.RATE_LIMIT_DELAY_S)

    def test_rate_limit_caps_long_retry_after_header(self, sleep) -> None:
        for retry_after in ("61", "600"):
            sleep.reset_mock()
            error = sdk_error(openrouter.errors.TooManyRequestsResponseError, headers={"retry-after": retry_after})
            function = mock.Mock(side_effect=[error, "result"])

            with self.subTest(retry_after=retry_after):
                self.assertEqual(openrouter_api._safe_run(function), "result")
                sleep.assert_called_once_with(openrouter_api.MAX_RATE_LIMIT_DELAY_S)

    def test_subclass_of_known_error_uses_parent_specs(self, sleep) -> None:
        # ConnectTimeout isn't listed itself, it's handled as its parent httpx.TransportError
        function = mock.Mock(side_effect=[httpx.ConnectTimeout("slow"), "result"])

        self.assertEqual(openrouter_api._safe_run(function), "result")
        sleep.assert_called_once_with(openrouter_api.RETRY_DELAY_S)

    def test_unknown_errors_are_not_caught(self, sleep) -> None:
        function = mock.Mock(side_effect=KeyError("bug"))

        with self.assertRaises(KeyError):
            openrouter_api._safe_run(function)

        sleep.assert_not_called()


def chat_result(content: str | None, refusal: str | None = None, finish_reason: str = "stop") -> SimpleNamespace:
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(model="model/x", choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


class ExtractResponseTests(unittest.TestCase):
    def test_returns_stripped_content(self) -> None:
        self.assertEqual(openrouter_api.extract_response_text(chat_result("  hi \n")), "hi")

    def test_falls_back_to_refusal(self) -> None:
        self.assertEqual(openrouter_api.extract_response_text(chat_result("", refusal="I can't.")), "I can't.")

    def test_rejects_missing_or_truncated_responses(self) -> None:
        responses = {
            "no choices": SimpleNamespace(model="model/x", choices=[]),
            "empty content": chat_result("   "),
            "token limit": chat_result(None, finish_reason="length"),
        }

        for case, response in responses.items():
            with self.subTest(case=case), self.assertRaises(ModelResponseError) as context:
                openrouter_api.extract_response_text(response)

            self.assertEqual(context.exception.model, "model/x")

    def test_extracts_usage(self) -> None:
        response = SimpleNamespace(usage=SimpleNamespace(total_tokens=42, cost=0.5))

        self.assertEqual(openrouter_api.extract_usage(response), (42, 0.5))

    def test_missing_usage_and_unset_cost_become_none(self) -> None:
        unset_cost = SimpleNamespace(usage=SimpleNamespace(total_tokens=42, cost=UNSET))

        self.assertEqual(openrouter_api.extract_usage(SimpleNamespace(usage=None)), (None, None))
        self.assertEqual(openrouter_api.extract_usage(unset_cost), (42, None))


if __name__ == "__main__":
    unittest.main()
