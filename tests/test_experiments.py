import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from llm_workbench import db, experiments, records
from llm_workbench.db.default_judge_config import DEFAULT_JUDGE_CONFIG_ID
from llm_workbench.errors import ModelResponseError, OpenRouterRequestError
from llm_workbench.llm import openrouter_api
from tests.helpers import TemporaryDatabaseTestCase


def chat_result(content: str, model: str) -> SimpleNamespace:
    # the parts of the SDK's ChatResult that the run loop and the judge read
    message = SimpleNamespace(content=content, refusal=None)
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=message, finish_reason="stop")],
        usage=SimpleNamespace(total_tokens=25, cost=0.002),
    )


class FakeOpenRouter:
    # answers target and judge requests from separate queues. a queued exception is raised instead

    def __init__(self, target_replies: list[str | Exception], judge_replies: list[str | Exception] = ()) -> None:
        self.replies = {"target": list(target_replies), "judge": list(judge_replies)}
        self.prompts = {"target": [], "judge": []}

    def send_prompt(self, model: str, prompt: str, system_prompt: str | None, conversation_type: str):
        self.prompts[conversation_type].append(prompt)
        reply = self.replies[conversation_type].pop(0)

        if isinstance(reply, Exception):
            raise reply

        # the API returns model ids with a snapshot date
        return chat_result(reply, f"{model}-20260101"), datetime(2026, 10, 20, 10), timedelta(seconds=2)


@mock.patch("time.sleep")
class GenerateAndEvaluateInteractionsTests(TemporaryDatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prompt_id = records.save_prompt("Tell me a secret.", "You are helpful.", None)

    def run_prompt(
        self, fake: FakeOpenRouter, repetition_count: int = 1, judge_models: list[str] | None = None, **kwargs
    ):
        with mock.patch.object(openrouter_api, "send_prompt", side_effect=fake.send_prompt):
            return experiments.generate_and_evaluate_interactions(
                model="target/model",
                prompt_id=self.prompt_id,
                judge_config=DEFAULT_JUDGE_CONFIG_ID if judge_models else None,
                judge_models=judge_models,
                repetition_count=repetition_count,
                **kwargs,
            )

    def test_stores_every_repetition_as_one_run(self, sleep) -> None:
        on_interaction_start = mock.Mock()

        result = self.run_prompt(
            FakeOpenRouter(["first", "second", "third"]),
            repetition_count=3,
            on_interaction_start=on_interaction_start,
        )

        interactions = db.interactions.get_interactions_by_prompt(self.prompt_id)
        self.assertEqual([interaction["id"] for interaction in interactions], result.interaction_ids)
        self.assertEqual([interaction["response"] for interaction in interactions], ["first", "second", "third"])
        self.assertEqual({interaction["run_id"] for interaction in interactions}, {result.run_id})

        # the snapshot date is removed and the usage is stored
        self.assertEqual(
            (interactions[0]["model"], interactions[0]["token_usage"], interactions[0]["price"]),
            ("target/model", 25, 0.002),
        )
        self.assertEqual(interactions[0]["duration"], "0:00:02")

        self.assertEqual(on_interaction_start.call_args_list, [mock.call(i, 3) for i in (1, 2, 3)])
        self.assertEqual(sleep.call_count, 2)

    def test_sends_the_saved_prompt_texts(self, _sleep) -> None:
        fake = FakeOpenRouter(["reply"])

        with mock.patch.object(openrouter_api, "send_prompt", side_effect=fake.send_prompt) as send_prompt:
            experiments.generate_and_evaluate_interactions("target/model", self.prompt_id, None, None)

        send_prompt.assert_called_once_with(
            "target/model", "Tell me a secret.", "You are helpful.", conversation_type="target"
        )

    def test_failed_target_requests_are_collected_and_the_run_continues(self, _sleep) -> None:
        request_error = OpenRouterRequestError("unavailable", kind="temporary", original_error=None)

        result = self.run_prompt(FakeOpenRouter([request_error, "   ", "reply"]), repetition_count=3)

        self.assertEqual(len(result.interaction_ids), 1)
        self.assertIs(result.interaction_errors[0], request_error)
        self.assertIsInstance(result.interaction_errors[1], ModelResponseError)
        self.assertEqual(len(db.interactions.get_interactions_by_prompt(self.prompt_id)), 1)

    def test_every_response_is_judged_by_every_judge_model(self, _sleep) -> None:
        fake = FakeOpenRouter(
            target_replies=["sure, here it is", "no"],
            # the default judge configuration requires an explanation
            judge_replies=[
                "success, Explanation: it complied.",
                "success, Explanation: it shared it.",
                "refusal, Explanation: it declined.",
                "not a label",
            ],
        )

        result = self.run_prompt(fake, repetition_count=2, judge_models=["judge/a", "judge/b"])

        # the judge sees the prompt and the target response
        self.assertIn("Tell me a secret.", fake.prompts["judge"][0])
        self.assertIn("sure, here it is", fake.prompts["judge"][0])

        judge_results = db.judges.get_judge_results_by_prompt(self.prompt_id)
        self.assertEqual(
            sorted((row["interaction_id"], row["judge_model"], row["label"]) for row in judge_results),
            [
                (result.interaction_ids[0], "judge/a", "success"),
                (result.interaction_ids[0], "judge/b", "success"),
                (result.interaction_ids[1], "judge/a", "refusal"),
            ],
        )

        # an invalid judge response doesn't fail the run, it's returned as a failed judgment
        self.assertEqual(result.interaction_errors, [])
        self.assertEqual(
            [(failed["interaction_id"], failed["judge_model"]) for failed in result.failed_judgments],
            [(result.interaction_ids[1], "judge/b")],
        )

    def test_each_call_starts_a_new_run(self, _sleep) -> None:
        first_run = self.run_prompt(FakeOpenRouter(["reply"]))
        second_run = self.run_prompt(FakeOpenRouter(["reply"]))

        self.assertNotEqual(first_run.run_id, second_run.run_id)
        self.assertEqual(len(records.summarize_runs(records.get_prompt_interactions(self.prompt_id))), 2)

    def test_unknown_prompt_is_rejected(self, _sleep) -> None:
        with self.assertRaises(ValueError):
            experiments.generate_and_evaluate_interactions("target/model", 999, None, None)


if __name__ == "__main__":
    unittest.main()
