import unittest
from datetime import date

import pandas as pd

from llm_workbench import analytics


class AnalyticsPreparationTests(unittest.TestCase):
    def test_empty_records_keep_stable_schemas(self) -> None:
        interactions = analytics.prepare_interactions([])
        judge_results = analytics.prepare_judge_results([])
        presets = analytics.prepare_presets([])

        self.assertEqual(list(interactions.columns), list(analytics.INTERACTION_COLUMNS))
        self.assertEqual(list(judge_results.columns), list(analytics.JUDGE_RESULT_COLUMNS))
        self.assertEqual(list(presets.columns), list(analytics.PRESET_COLUMNS))
        self.assertTrue(interactions.empty)
        self.assertTrue(judge_results.empty)
        self.assertTrue(presets.empty)

    def test_interactions_parse_database_values_without_mutating_input(self) -> None:
        source = pd.DataFrame([
            {
                "id": 1,
                "time": "2026-09-20 10:00:00",
                "model": "model/a",
                "categories": '["one", "two"]',
                "duration": "0:00:02.500000",
                "token_usage": "12",
                "price": "0.25",
            },
            {
                "id": 2,
                "time": "invalid",
                "model": "model/b",
                "categories": None,
                "duration": None,
                "token_usage": None,
                "price": None,
            },
        ])

        interactions = analytics.prepare_interactions(source)

        self.assertEqual(interactions.loc[0, "categories"], ["one", "two"])
        self.assertEqual(interactions.loc[1, "categories"], [])
        self.assertEqual(interactions.loc[0, "duration"], pd.Timedelta(seconds=2.5))
        self.assertEqual(interactions.loc[0, "token_usage"], 12)
        self.assertEqual(interactions.loc[0, "price"], 0.25)
        self.assertTrue(pd.isna(interactions.loc[1, "time"]))
        self.assertEqual(source.loc[0, "categories"], '["one", "two"]')

    def test_judge_results_and_presets_parse_database_values(self) -> None:
        judge_results = analytics.prepare_judge_results([
            {
                "id": 1,
                "time": "2026-09-20 10:00:00",
                "duration": "0:00:01.250000",
                "price": "0.05",
            },
        ])
        presets = analytics.prepare_presets([
            {
                "id": 1,
                "categories": '["alpha", null, 5]',
                "created_at": "2026-09-20 09:00:00",
            },
        ])

        self.assertEqual(judge_results.loc[0, "duration"], pd.Timedelta(seconds=1.25))
        self.assertEqual(judge_results.loc[0, "price"], 0.05)
        self.assertEqual(presets.loc[0, "categories"], ["alpha"])
        self.assertEqual(presets.loc[0, "created_at"], pd.Timestamp("2026-09-20 09:00:00"))


class AnalyticsFilteringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.interactions = analytics.prepare_interactions([
            {
                "id": 1,
                "time": "2026-09-19 10:00:00",
                "model": "model/a",
                "categories": '["alpha"]',
            },
            {
                "id": 2,
                "time": "2026-09-20 10:00:00",
                "model": "model/a",
                "categories": '["beta", "gamma"]',
            },
            {
                "id": 3,
                "time": "2026-09-21 10:00:00",
                "model": "model/b",
                "categories": None,
            },
        ])

    def test_interaction_filters_are_combined(self) -> None:
        filtered = analytics.filter_interactions(
            self.interactions,
            start_date=date(2026, 9, 20),
            end_date=date(2026, 9, 21),
            models=["model/a"],
            categories=["gamma"],
        )

        self.assertEqual(filtered["id"].tolist(), [2])
        self.assertEqual(len(self.interactions), 3)

    def test_empty_filter_selection_matches_no_rows(self) -> None:
        filtered = analytics.filter_interactions(self.interactions, models=[])

        self.assertTrue(filtered.empty)

    def test_invalid_date_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analytics.filter_interactions(
                self.interactions,
                start_date=date(2026, 9, 21),
                end_date=date(2026, 9, 20),
            )

    def test_judge_filters_follow_filtered_interactions(self) -> None:
        judge_results = analytics.prepare_judge_results([
            {
                "id": 1,
                "interaction_id": 1,
                "judge_config_id": "config-a",
                "judge_model": "judge/a",
            },
            {
                "id": 2,
                "interaction_id": 2,
                "judge_config_id": "config-b",
                "judge_model": "judge/b",
            },
        ])

        filtered = analytics.filter_judge_results(
            judge_results,
            interaction_ids=[2],
            judge_config_ids=["config-b"],
            judge_models=["judge/b"],
        )

        self.assertEqual(filtered["id"].tolist(), [2])


class AnalyticsAggregationTests(unittest.TestCase):
    def test_latest_judge_result_is_selected_per_setup(self) -> None:
        judge_results = analytics.prepare_judge_results([
            {
                "id": 1,
                "interaction_id": 10,
                "judge_config_id": "config",
                "judge_model": "judge/a",
                "label": "refusal",
                "time": "2026-09-20 10:00:00",
            },
            {
                "id": 2,
                "interaction_id": 10,
                "judge_config_id": "config",
                "judge_model": "judge/a",
                "label": "success",
                "time": "2026-09-20 11:00:00",
            },
            {
                "id": 3,
                "interaction_id": 10,
                "judge_config_id": "config",
                "judge_model": "judge/b",
                "label": "unclear",
                "time": "2026-09-20 11:00:00",
            },
            {
                "id": 4,
                "interaction_id": 10,
                "judge_config_id": "config",
                "judge_model": "judge/a",
                "label": "refusal",
                "time": "2026-09-20 11:00:00",
            },
        ])

        latest = analytics.get_latest_judge_results(judge_results)

        self.assertEqual(latest["id"].tolist(), [3, 4])
        self.assertEqual(latest["label"].tolist(), ["unclear", "refusal"])

    def test_exploded_categories_keep_every_membership(self) -> None:
        interactions = analytics.prepare_interactions([
            {"id": 1, "categories": '["alpha", "beta"]'},
            {"id": 2, "categories": None},
        ])

        exploded = analytics.explode_categories(interactions)

        self.assertEqual(exploded["category"].tolist(), ["alpha", "beta"])
        self.assertEqual(interactions.loc[0, "categories"], ["alpha", "beta"])

    def test_label_summary_has_stable_order_and_ignores_missing_labels(self) -> None:
        distribution = analytics.summarize_labels(
            pd.Series(["success", "success", "refusal", None, "invalid"])
        )

        self.assertEqual(distribution["label"].tolist(), list(analytics.LABELS))
        self.assertEqual(distribution["count"].tolist(), [2, 1, 0])
        self.assertAlmostEqual(distribution["percentage"].sum(), 100.0)

    def test_activity_and_cost_summaries_group_values_by_date(self) -> None:
        interactions = analytics.prepare_interactions([
            {"id": 1, "time": "2026-09-20 10:00:00", "price": 0.10},
            {"id": 2, "time": "2026-09-20 12:00:00", "price": 0.20},
            {"id": 3, "time": "2026-09-21 10:00:00", "price": None},
        ])
        judge_results = analytics.prepare_judge_results([
            {"id": 1, "time": "2026-09-20 10:01:00", "price": 0.01},
            {"id": 2, "time": "2026-09-22 10:00:00", "price": 0.02},
        ])

        activity = analytics.summarize_activity(interactions)
        costs = analytics.summarize_costs(interactions, judge_results)

        self.assertEqual(activity["interaction_count"].tolist(), [2, 1])
        self.assertEqual(costs["date"].dt.day.tolist(), [20, 21, 22])
        self.assertAlmostEqual(costs.loc[0, "target_cost"], 0.30)
        self.assertAlmostEqual(costs.loc[0, "judging_cost"], 0.01)
        self.assertAlmostEqual(costs.loc[0, "total_cost"], 0.31)
        self.assertEqual(costs.loc[1:, "target_cost"].tolist(), [0.0, 0.0])
        self.assertEqual(costs.loc[1:, "judging_cost"].tolist(), [0.0, 0.02])
        self.assertEqual(costs.loc[1:, "total_cost"].tolist(), [0.0, 0.02])

    def test_label_records_keep_only_supported_labels(self) -> None:
        interactions = analytics.prepare_interactions([
            {"id": 1, "manual_label": "success"},
            {"id": 2, "manual_label": "invalid"},
            {"id": 3, "manual_label": None},
        ])
        judge_results = analytics.prepare_judge_results([
            {"id": 1, "interaction_id": 1, "label": "refusal"},
            {"id": 2, "interaction_id": 1, "label": "unclear"},
            {"id": 3, "interaction_id": 2, "label": None},
        ])

        manual_labels = analytics.get_manual_label_records(interactions)
        judge_labels = analytics.get_judge_label_records(judge_results)

        self.assertEqual(manual_labels.to_dict("records"), [
            {"interaction_id": 1, "label": "success"},
        ])
        self.assertEqual(judge_labels.to_dict("records"), [
            {"interaction_id": 1, "label": "refusal"},
            {"interaction_id": 1, "label": "unclear"},
        ])

    def test_model_summary_separates_interactions_from_labels(self) -> None:
        interactions = analytics.prepare_interactions([
            {
                "id": 1,
                "model": "model/a",
                "categories": '["alpha", "beta"]',
                "duration": "0:00:02",
                "token_usage": 10,
                "price": 0.10,
            },
            {
                "id": 2,
                "model": "model/a",
                "categories": '["alpha"]',
                "duration": "0:00:04",
                "token_usage": 30,
                "price": 0.30,
            },
            {
                "id": 3,
                "model": "model/b",
                "categories": '["beta"]',
                "duration": "0:00:06",
                "token_usage": 50,
                "price": None,
            },
        ])
        label_records = pd.DataFrame([
            {"interaction_id": 1, "label": "success"},
            {"interaction_id": 1, "label": "refusal"},
            {"interaction_id": 2, "label": "success"},
        ])

        summary = analytics.summarize_models(interactions, label_records)
        model_a = summary.loc[summary["model"] == "model/a"].iloc[0]
        model_b = summary.loc[summary["model"] == "model/b"].iloc[0]

        self.assertEqual(model_a["interaction_count"], 2)
        self.assertEqual(model_a["label_count"], 3)
        self.assertEqual(model_a["success_count"], 2)
        self.assertEqual(model_a["refusal_count"], 1)
        self.assertAlmostEqual(model_a["success_share"], 200 / 3)
        self.assertEqual(model_a["median_duration_seconds"], 3.0)
        self.assertEqual(model_a["median_tokens"], 20)
        self.assertAlmostEqual(model_a["total_cost"], 0.40)
        self.assertAlmostEqual(model_a["average_cost"], 0.20)
        self.assertEqual(model_b["interaction_count"], 1)
        self.assertEqual(model_b["label_count"], 0)
        self.assertTrue(pd.isna(model_b["success_share"]))

    def test_category_summaries_keep_every_category_membership(self) -> None:
        interactions = analytics.prepare_interactions([
            {"id": 1, "model": "model/a", "categories": '["alpha", "beta"]'},
            {"id": 2, "model": "model/a", "categories": '["alpha"]'},
            {"id": 3, "model": "model/b", "categories": '["beta"]'},
        ])
        label_records = pd.DataFrame([
            {"interaction_id": 1, "label": "success"},
            {"interaction_id": 1, "label": "refusal"},
            {"interaction_id": 2, "label": "success"},
        ])

        categories = analytics.summarize_categories(interactions, label_records)
        model_categories = analytics.summarize_model_categories(
            interactions,
            label_records,
        )
        alpha = categories.loc[categories["category"] == "alpha"].iloc[0]
        beta = categories.loc[categories["category"] == "beta"].iloc[0]
        model_a_beta = model_categories.loc[
            (model_categories["model"] == "model/a")
            & (model_categories["category"] == "beta")
        ].iloc[0]
        model_b_beta = model_categories.loc[
            (model_categories["model"] == "model/b")
            & (model_categories["category"] == "beta")
        ].iloc[0]

        self.assertEqual(alpha["interaction_count"], 2)
        self.assertEqual(alpha["label_count"], 3)
        self.assertEqual(beta["interaction_count"], 2)
        self.assertEqual(beta["label_count"], 2)
        self.assertEqual(model_a_beta["interaction_count"], 1)
        self.assertEqual(model_a_beta["label_count"], 2)
        self.assertEqual(model_b_beta["interaction_count"], 1)
        self.assertEqual(model_b_beta["label_count"], 0)

    def test_judge_summary_uses_all_costs_and_latest_outcomes(self) -> None:
        judge_results = analytics.prepare_judge_results([
            {
                "id": 1,
                "interaction_id": 1,
                "judge_config_id": "config-a",
                "judge_model": "judge/a",
                "label": "refusal",
                "time": "2026-09-20 10:00:00",
                "duration": "0:00:01",
                "price": 0.01,
            },
            {
                "id": 2,
                "interaction_id": 1,
                "judge_config_id": "config-a",
                "judge_model": "judge/a",
                "label": "success",
                "time": "2026-09-20 11:00:00",
                "duration": "0:00:03",
                "price": 0.02,
            },
            {
                "id": 3,
                "interaction_id": 2,
                "judge_config_id": "config-a",
                "judge_model": "judge/a",
                "label": "success",
                "time": "2026-09-20 12:00:00",
                "duration": "0:00:05",
                "price": 0.03,
            },
            {
                "id": 4,
                "interaction_id": 1,
                "judge_config_id": "config-a",
                "judge_model": "judge/b",
                "label": "success",
                "time": "2026-09-20 11:00:00",
                "duration": "0:00:02",
                "price": 0.04,
            },
            {
                "id": 5,
                "interaction_id": 2,
                "judge_config_id": "config-a",
                "judge_model": "judge/b",
                "label": "refusal",
                "time": "2026-09-20 12:00:00",
                "duration": "0:00:04",
                "price": 0.05,
            },
        ])

        summary = analytics.summarize_judges(judge_results)
        judge_a = summary.loc[summary["judge_model"] == "judge/a"].iloc[0]
        judge_b = summary.loc[summary["judge_model"] == "judge/b"].iloc[0]

        self.assertEqual(judge_a["evaluation_count"], 3)
        self.assertEqual(judge_a["interaction_count"], 2)
        self.assertEqual(judge_a["label_count"], 2)
        self.assertEqual(judge_a["success_count"], 2)
        self.assertEqual(judge_a["refusal_count"], 0)
        self.assertEqual(judge_a["median_duration_seconds"], 3.0)
        self.assertAlmostEqual(judge_a["total_cost"], 0.06)
        self.assertAlmostEqual(judge_a["average_cost"], 0.02)
        self.assertEqual(judge_b["label_count"], 2)
        self.assertEqual(judge_b["success_count"], 1)
        self.assertEqual(judge_b["refusal_count"], 1)

    def test_judge_agreement_uses_overlapping_latest_labels(self) -> None:
        judge_results = analytics.prepare_judge_results([
            {
                "id": 1,
                "interaction_id": 1,
                "judge_config_id": "config-a",
                "judge_model": "judge/a",
                "label": "refusal",
                "time": "2026-09-20 10:00:00",
            },
            {
                "id": 2,
                "interaction_id": 1,
                "judge_config_id": "config-a",
                "judge_model": "judge/a",
                "label": "success",
                "time": "2026-09-20 11:00:00",
            },
            {
                "id": 3,
                "interaction_id": 2,
                "judge_config_id": "config-a",
                "judge_model": "judge/a",
                "label": "success",
                "time": "2026-09-20 12:00:00",
            },
            {
                "id": 4,
                "interaction_id": 1,
                "judge_config_id": "config-a",
                "judge_model": "judge/b",
                "label": "success",
                "time": "2026-09-20 11:00:00",
            },
            {
                "id": 5,
                "interaction_id": 2,
                "judge_config_id": "config-a",
                "judge_model": "judge/b",
                "label": "refusal",
                "time": "2026-09-20 12:00:00",
            },
            {
                "id": 6,
                "interaction_id": 3,
                "judge_config_id": "config-a",
                "judge_model": "judge/c",
                "label": "unclear",
                "time": "2026-09-20 12:00:00",
            },
        ])

        agreement = analytics.summarize_judge_agreement(judge_results)
        setup_a = "judge/a · config-a"
        setup_b = "judge/b · config-a"
        setup_c = "judge/c · config-a"
        a_to_b = agreement.loc[
            (agreement["judge_a"] == setup_a)
            & (agreement["judge_b"] == setup_b)
        ].iloc[0]
        a_to_a = agreement.loc[
            (agreement["judge_a"] == setup_a)
            & (agreement["judge_b"] == setup_a)
        ].iloc[0]
        a_to_c = agreement.loc[
            (agreement["judge_a"] == setup_a)
            & (agreement["judge_b"] == setup_c)
        ].iloc[0]

        self.assertEqual(a_to_b["overlap_count"], 2)
        self.assertEqual(a_to_b["agreement_count"], 1)
        self.assertEqual(a_to_b["agreement_share"], 50.0)
        self.assertEqual(a_to_a["overlap_count"], 2)
        self.assertEqual(a_to_a["agreement_share"], 100.0)
        self.assertEqual(a_to_c["overlap_count"], 0)
        self.assertTrue(pd.isna(a_to_c["agreement_share"]))

    def test_overview_counts_all_judgment_costs(self) -> None:
        interactions = analytics.prepare_interactions([
            {
                "id": 1,
                "model": "model/a",
                "categories": '["alpha", "beta"]',
                "manual_label": "success",
                "duration": "0:00:02",
                "token_usage": 10,
                "price": 0.10,
            },
            {
                "id": 2,
                "model": "model/b",
                "categories": None,
                "manual_label": None,
                "duration": "0:00:04",
                "token_usage": None,
                "price": None,
            },
        ])
        judge_results = analytics.prepare_judge_results([
            {"id": 1, "interaction_id": 1, "price": 0.01},
            {"id": 2, "interaction_id": 1, "price": 0.02},
            {"id": 3, "interaction_id": 2, "price": None},
        ])

        metrics = analytics.get_overview_metrics(interactions, judge_results)

        self.assertEqual(metrics.interaction_count, 2)
        self.assertEqual(metrics.target_model_count, 2)
        self.assertEqual(metrics.category_count, 2)
        self.assertEqual(metrics.categorized_interaction_count, 1)
        self.assertEqual(metrics.manually_labeled_interaction_count, 1)
        self.assertEqual(metrics.judged_interaction_count, 2)
        self.assertEqual(metrics.judgment_count, 3)
        self.assertAlmostEqual(metrics.target_cost, 0.10)
        self.assertAlmostEqual(metrics.judging_cost, 0.03)
        self.assertEqual(metrics.token_usage, 10)
        self.assertEqual(metrics.median_duration_seconds, 3.0)

    def test_empty_overview_has_zero_values(self) -> None:
        metrics = analytics.get_overview_metrics(
            analytics.prepare_interactions([]),
            analytics.prepare_judge_results([]),
        )

        self.assertEqual(metrics.interaction_count, 0)
        self.assertEqual(metrics.target_cost, 0.0)
        self.assertEqual(metrics.token_usage, 0)
        self.assertIsNone(metrics.median_duration_seconds)


if __name__ == "__main__":
    unittest.main()
