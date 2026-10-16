import unittest

from llm_workbench import records


def interaction(interaction_id: int, run_id: str, time: str, model: str, manual_label: str | None) -> dict:
    return {
        "interaction": {
            "id": interaction_id,
            "run_id": run_id,
            "time": time,
            "model": model,
            "manual_label": manual_label,
        },
        "judge_results": [],
    }


INTERACTIONS = [
    interaction(1, "b", "2026-10-16 12:00:00", "model/x", "success"),
    interaction(2, "a", "2026-10-16 10:00:00", "model/y", None),
    interaction(3, "a", "2026-10-16 10:00:05", "model/x", "refusal"),
]


def ids(prompt_interactions: list[dict]) -> list[int]:
    return [i["interaction"]["id"] for i in prompt_interactions]


class RunSummaryTests(unittest.TestCase):
    def test_runs_are_numbered_by_start_time(self) -> None:
        self.assertEqual(
            records.summarize_runs(INTERACTIONS),
            [
                {"run_id": "a", "number": 1, "started_at": "2026-10-16 10:00:00", "interaction_count": 2},
                {"run_id": "b", "number": 2, "started_at": "2026-10-16 12:00:00", "interaction_count": 1},
            ],
        )

    def test_no_interactions_have_no_runs(self) -> None:
        self.assertEqual(records.summarize_runs([]), [])


class InteractionFilterTests(unittest.TestCase):
    def test_empty_filters_keep_everything(self) -> None:
        self.assertEqual(ids(records.filter_prompt_interactions(INTERACTIONS)), [1, 2, 3])

    def test_filter_by_run(self) -> None:
        self.assertEqual(ids(records.filter_prompt_interactions(INTERACTIONS, run_id="a")), [2, 3])

    def test_filter_by_model(self) -> None:
        self.assertEqual(ids(records.filter_prompt_interactions(INTERACTIONS, models=["model/x"])), [1, 3])

    def test_none_label_selects_unlabeled(self) -> None:
        self.assertEqual(ids(records.filter_prompt_interactions(INTERACTIONS, manual_labels=[None, "refusal"])), [2, 3])

    def test_filters_are_combined(self) -> None:
        self.assertEqual(
            ids(records.filter_prompt_interactions(INTERACTIONS, run_id="a", models=["model/x"], manual_labels=["success"])),
            [],
        )


if __name__ == "__main__":
    unittest.main()
