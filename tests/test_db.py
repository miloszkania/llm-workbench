import sqlite3
import unittest

from llm_workbench import db, records
from llm_workbench.db.connection import connect, fetch_all
from llm_workbench.db.default_judge_config import DEFAULT_JUDGE_CONFIG_ID
from tests.helpers import TemporaryDatabaseTestCase


def add_interaction(prompt_id: int, run_id: str = "run", time: str = "2026-10-20 10:00:00") -> int:
    return db.interactions.insert_interaction(
        {
            "prompt_id": prompt_id,
            "run_id": run_id,
            "time": time,
            "model": "model/x",
            "response": "response",
            "duration": "0:00:01",
            "token_usage": 10,
            "price": 0.001,
        }
    )


def add_judge_result(interaction_id: int, label: str = "success") -> None:
    db.judges.insert_judge_result(
        {
            "interaction_id": interaction_id,
            "judge_config_id": DEFAULT_JUDGE_CONFIG_ID,
            "judge_model": "judge/model",
            "label": label,
            "explanation": None,
            "time": "2026-10-20 10:00:01",
            "duration": "0:00:01",
            "price": 0.0001,
        }
    )


def count_rows(table: str) -> int:
    # table names come only from the tests themselves
    return fetch_all(f"select count(*) as count from {table}")[0]["count"]


class ConnectionTests(TemporaryDatabaseTestCase):
    def test_new_database_contains_the_default_judge_configuration(self) -> None:
        self.assertEqual(db.judges.get_saved_configuration_ids(), [DEFAULT_JUDGE_CONFIG_ID])

    def test_rolls_back_when_an_error_occurs(self) -> None:
        with self.assertRaises(RuntimeError), connect() as connection:
            connection.execute("insert into prompts (prompt) values ('hello')")
            raise RuntimeError("something failed after the insert")

        self.assertEqual(count_rows("prompts"), 0)

    def test_foreign_keys_are_enforced(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            add_interaction(prompt_id=999)

    def test_check_constraints_reject_invalid_values(self) -> None:
        interaction_id = add_interaction(records.save_prompt("hello", None, None))

        with self.assertRaises(sqlite3.IntegrityError):
            db.interactions.set_interaction_label(interaction_id, "jailbroken")


class PromptTests(TemporaryDatabaseTestCase):
    def test_same_texts_are_saved_as_one_prompt(self) -> None:
        # surrounding whitespace and a missing system prompt don't make a prompt distinct
        first_id = records.save_prompt("hello", None, None)
        second_id = records.save_prompt("  hello \n", "", None)

        self.assertEqual(first_id, second_id)
        self.assertEqual(count_rows("prompts"), 1)

    def test_different_system_prompt_is_a_different_prompt(self) -> None:
        self.assertNotEqual(records.save_prompt("hello", None, None), records.save_prompt("hello", "be brief", None))

    def test_saving_again_keeps_categories_unless_new_ones_are_passed(self) -> None:
        prompt_id = records.save_prompt("hello", None, ["a"])

        records.save_prompt("hello", None, None)
        self.assertEqual(db.prompts.get_prompt_by_id(prompt_id)["categories"], '["a"]')

        records.save_prompt("hello", None, ["b"])
        self.assertEqual(db.prompts.get_prompt_by_id(prompt_id)["categories"], '["b"]')

    def test_empty_prompt_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            records.save_prompt("   ", "system prompt", None)

    def test_overview_counts_runs_responses_and_labels(self) -> None:
        prompt_id = records.save_prompt("hello", None, None)
        unused_prompt_id = records.save_prompt("never run", None, None)

        for run_id, label, time in (
            ("run-1", "success", "2026-10-20 10:00:00"),
            ("run-1", "refusal", "2026-10-20 10:00:05"),
            ("run-2", None, "2026-10-21 09:00:00"),
        ):
            db.interactions.set_interaction_label(add_interaction(prompt_id, run_id, time), label)

        overview = {row["id"]: row for row in db.prompts.get_prompt_overview()}

        self.assertEqual(overview[prompt_id]["run_count"], 2)
        self.assertEqual(overview[prompt_id]["interaction_count"], 3)
        self.assertEqual(
            (overview[prompt_id]["success_count"], overview[prompt_id]["refusal_count"]),
            (1, 1),
        )
        self.assertEqual(overview[prompt_id]["last_run_at"], "2026-10-21 09:00:00")
        self.assertEqual(overview[unused_prompt_id]["interaction_count"], 0)
        self.assertIsNone(overview[unused_prompt_id]["last_run_at"])


class InteractionTests(TemporaryDatabaseTestCase):
    def test_interactions_carry_their_prompt_in_time_order(self) -> None:
        prompt_id = records.save_prompt("hello", "be brief", ["a"])
        later_id = add_interaction(prompt_id, time="2026-10-20 12:00:00")
        earlier_id = add_interaction(prompt_id, time="2026-10-20 08:00:00")
        add_interaction(records.save_prompt("other prompt", None, None))

        interactions = db.interactions.get_interactions_by_prompt(prompt_id)

        self.assertEqual([interaction["id"] for interaction in interactions], [earlier_id, later_id])
        self.assertEqual(
            (interactions[0]["prompt"], interactions[0]["system_prompt"], interactions[0]["categories"]),
            ("hello", "be brief", '["a"]'),
        )

    def test_deleting_a_prompt_deletes_its_interactions_and_judge_results(self) -> None:
        prompt_id = records.save_prompt("hello", None, None)
        add_judge_result(add_interaction(prompt_id))
        kept_interaction_id = add_interaction(records.save_prompt("other prompt", None, None))
        add_judge_result(kept_interaction_id)

        db.prompts.delete_prompt(prompt_id)

        self.assertEqual([row["id"] for row in db.interactions.get_all_interactions()], [kept_interaction_id])
        self.assertEqual(count_rows("judge_results"), 1)

    def test_deleting_an_interaction_deletes_its_judge_results(self) -> None:
        prompt_id = records.save_prompt("hello", None, None)
        interaction_id = add_interaction(prompt_id)
        add_judge_result(interaction_id, "success")
        add_judge_result(interaction_id, "refusal")

        db.interactions.delete_interaction(interaction_id)

        self.assertEqual(db.judges.get_judge_results_by_prompt(prompt_id), [])


class SettingsTests(TemporaryDatabaseTestCase):
    def test_settings_are_empty_in_a_new_database(self) -> None:
        self.assertEqual(db.settings.get_default_judge_settings(), (None, []))
        self.assertEqual(db.settings.get_favorite_models(), [])

    def test_saved_settings_overwrite_the_previous_ones(self) -> None:
        db.settings.modify_default_judge_settings("config-a", ["judge/a"])
        db.settings.modify_default_judge_settings("config-b", ["judge/b", "judge/c"])
        db.settings.update_favorite_models(["model/x"])
        db.settings.update_favorite_models(["model/y"])

        self.assertEqual(db.settings.get_default_judge_settings(), ("config-b", ["judge/b", "judge/c"]))
        self.assertEqual(db.settings.get_favorite_models(), ["model/y"])


if __name__ == "__main__":
    unittest.main()
