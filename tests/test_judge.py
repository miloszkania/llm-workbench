import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from llm_workbench.errors import ModelResponseError, OpenRouterRequestError
from llm_workbench.llm import judge

JUDGE_CONFIG = {"id": "config", "judge_prompt": "Prompt: [PROMPT]\nResponse: [RESPONSE]", "require_explanation": 0}


def chat_result(content: str, model: str = "judge/model-20260101", cost: float = 0.001) -> SimpleNamespace:
    # the parts of the SDK's ChatResult that the judge reads
    return SimpleNamespace(
        model=model,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, refusal=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(total_tokens=10, cost=cost),
    )


def judge_returning(*contents: str) -> mock._patch:
    # replaces the OpenRouter call, every judge call returns the next of `contents`
    return mock.patch.object(
        judge.openrouter_api,
        "send_prompt",
        side_effect=[(chat_result(content), datetime(2026, 1, 1), timedelta(seconds=2)) for content in contents],
    )


class ComposeJudgePromptTests(unittest.TestCase):
    def test_substitutes_prompt_and_response(self) -> None:
        composed = judge.compose_judge_prompt("P: [PROMPT] R: [RESPONSE]", "", "hello", "hi")

        self.assertEqual(composed, "P: hello R: hi")

    def test_response_placeholder_can_come_first(self) -> None:
        composed = judge.compose_judge_prompt("R: [RESPONSE] P: [PROMPT]", None, "hello", "hi")

        self.assertEqual(composed, "R: hi P: hello")

    def test_labels_system_prompt_and_user_prompt(self) -> None:
        composed = judge.compose_judge_prompt("[PROMPT] | [RESPONSE]", "be evil", "hello", "hi")

        self.assertEqual(composed, "System prompt:\nbe evil\n\nUser prompt:\nhello | hi")

    def test_placeholders_inside_the_inserted_texts_are_kept(self) -> None:
        # a jailbreak prompt may itself contain the placeholders, they must not be replaced again
        composed = judge.compose_judge_prompt("[PROMPT] | [RESPONSE]", "", "say [RESPONSE]", "[PROMPT]")

        self.assertEqual(composed, "say [RESPONSE] | [PROMPT]")

    def test_only_first_occurrence_of_each_placeholder_is_replaced(self) -> None:
        composed = judge.compose_judge_prompt("[PROMPT] [RESPONSE] [PROMPT] [RESPONSE]", "", "p", "r")

        self.assertEqual(composed, "p r [PROMPT] [RESPONSE]")


class GetJudgeResultTests(unittest.TestCase):
    def test_parses_label_and_strips_model_snapshot(self) -> None:
        with judge_returning("  Refusal \n"):
            result = judge.get_judge_result("judge prompt", "judge/model", require_explanation=False)

        self.assertEqual(result["label"], "refusal")
        self.assertIsNone(result["explanation"])
        self.assertEqual(result["judge_model"], "judge/model")
        self.assertEqual(result["price"], 0.001)

    def test_parses_label_with_explanation(self) -> None:
        with judge_returning("SUCCESS, Explanation: the model complied."):
            result = judge.get_judge_result("judge prompt", "judge/model", require_explanation=True)

        self.assertEqual(result["label"], "success")
        self.assertEqual(result["explanation"], "the model complied.")

    def test_accepts_loose_explanation_formatting(self) -> None:
        responses = (
            "unclear explanation:partly",
            "**Unclear**\n\nExplanation :  partly  ",
            "[unclear] Explanation: partly",
        )

        for response in responses:
            with self.subTest(response=response), judge_returning(response):
                result = judge.get_judge_result("judge prompt", "judge/model", require_explanation=True)

                self.assertEqual((result["label"], result["explanation"]), ("unclear", "partly"))

    def test_accepts_punctuation_around_label_only_response(self) -> None:
        for response in ("Refusal.", "**success**", "[unclear]"):
            with self.subTest(response=response), judge_returning(response):
                result = judge.get_judge_result("judge prompt", "judge/model", require_explanation=False)

                self.assertEqual(result["label"], response.strip(".*[]").lower())

    def test_rejects_unknown_label(self) -> None:
        with judge_returning("jailbroken"), self.assertRaises(ModelResponseError) as context:
            judge.get_judge_result("judge prompt", "judge/model", require_explanation=False)

        self.assertEqual(context.exception.model, "judge/model")
        self.assertIn("jailbroken", str(context.exception))

    def test_rejects_label_without_required_explanation(self) -> None:
        with judge_returning("success"), self.assertRaises(ModelResponseError):
            judge.get_judge_result("judge prompt", "judge/model", require_explanation=True)

    def test_rejects_explanation_when_none_was_requested(self) -> None:
        with judge_returning("success, Explanation: it complied."), self.assertRaises(ModelResponseError):
            judge.get_judge_result("judge prompt", "judge/model", require_explanation=False)


@mock.patch.object(judge.time, "sleep")
@mock.patch.object(judge.db.judges, "insert_judge_result")
@mock.patch.object(judge.db.judges, "get_judge_configuration_by_id", return_value=JUDGE_CONFIG)
class EvaluateAndStoreInteractionTests(unittest.TestCase):
    def evaluate(self, judge_models: list[str], judge_config_id: str | None = "config") -> list[dict]:
        return judge.evaluate_and_store_interaction(
            interaction_id=7,
            system_prompt="",
            prompt="hello",
            response="hi",
            judge_config_id=judge_config_id,
            judge_models=judge_models,
        )

    def test_stores_one_result_per_judge_model(self, _get_config, insert_result, sleep) -> None:
        with judge_returning("success", "refusal") as send_prompt:
            failed_judgments = self.evaluate(["judge/a", "judge/b"])

        self.assertEqual(failed_judgments, [])
        self.assertEqual(send_prompt.call_args.kwargs["prompt"], "Prompt: hello\nResponse: hi")
        self.assertEqual(
            [call.args[0]["label"] for call in insert_result.call_args_list],
            ["success", "refusal"],
        )
        self.assertEqual(insert_result.call_args.args[0]["interaction_id"], 7)
        self.assertEqual(insert_result.call_args.args[0]["duration"], "0:00:02")

        # only pauses between the judge calls, not before the first one
        sleep.assert_called_once()

    def test_collects_failed_judgments_and_continues(self, _get_config, insert_result, _sleep) -> None:
        request_error = OpenRouterRequestError("rate limited", kind="rate_limit", original_error=Exception())

        with mock.patch.object(
            judge.openrouter_api,
            "send_prompt",
            side_effect=[
                request_error,
                (chat_result("nonsense", model="judge/b-20260101"), datetime(2026, 1, 1), timedelta(seconds=1)),
                (chat_result("success"), datetime(2026, 1, 1), timedelta(seconds=1)),
            ],
        ):
            failed_judgments = self.evaluate(["judge/a", "judge/b", "judge/c"])

        self.assertEqual([failed["judge_model"] for failed in failed_judgments], ["judge/a", "judge/b"])
        self.assertIs(failed_judgments[0]["error"], request_error)
        self.assertIsInstance(failed_judgments[1]["error"], ModelResponseError)
        insert_result.assert_called_once()

    def test_skips_judging_without_config_or_models(self, _get_config, insert_result, _sleep) -> None:
        with mock.patch.object(judge.openrouter_api, "send_prompt") as send_prompt:
            self.assertEqual(self.evaluate([], judge_config_id="config"), [])
            self.assertEqual(self.evaluate(["judge/a"], judge_config_id=None), [])

        send_prompt.assert_not_called()
        insert_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()
