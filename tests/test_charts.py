import unittest

import pandas as pd

from llm_workbench.analytics import charts, stats


class ChartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model_categories = pd.DataFrame(
            [
                {
                    "model": "model/a",
                    "category": "one",
                    "interaction_count": 4,
                    "success_count": 3,
                    "refusal_count": 1,
                    "unclear_count": 0,
                    "label_count": 4,
                    "success_share": 75.0,
                },
                {
                    "model": "model/b",
                    "category": "two",
                    "interaction_count": 2,
                    "success_count": 0,
                    "refusal_count": 2,
                    "unclear_count": 0,
                    "label_count": 2,
                    "success_share": 0.0,
                },
            ]
        )

    def test_share_heatmap_follows_requested_order_and_leaves_missing_cells_empty(self) -> None:
        figure = charts.create_model_category_heatmap(
            self.model_categories,
            model_order=["model/b", "model/a"],
            category_order=["one", "two"],
        )
        heatmap = figure.data[0]

        self.assertEqual(list(heatmap.y), ["model/b", "model/a"])
        self.assertEqual(list(heatmap.x), ["one", "two"])
        self.assertEqual(list(heatmap.text[0]), ["", "0%<br>n=2"])
        self.assertEqual(list(heatmap.text[1]), ["75%<br>n=4", ""])
        # label count, success, refusal and unclear counts are available on hover
        self.assertEqual(list(heatmap.customdata[1][0]), [4, 3, 1, 0])

    def test_group_label_distribution_hides_small_segment_text(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "model": "model/a",
                    "success_count": 1,
                    "refusal_count": 39,
                    "unclear_count": 0,
                    "label_count": 40,
                }
            ]
        )

        figure = charts.create_group_label_distribution_chart(summary, "model")
        texts = {trace.name: trace.text[0] for trace in figure.data}

        self.assertEqual(texts, {"success": "", "refusal": "98%", "unclear": ""})

    def test_export_preparation_does_not_modify_the_dashboard_figure(self) -> None:
        activity = stats.summarize_activity(
            stats.prepare_interactions(
                [
                    {"id": 1, "time": "2026-09-20 10:00:00"},
                ]
            )
        )
        figure = charts.create_activity_chart(activity)

        export_figure = charts.prepare_chart_for_export(figure)

        self.assertTrue(export_figure.layout.xaxis.automargin)
        self.assertIsNone(figure.layout.xaxis.automargin)


if __name__ == "__main__":
    unittest.main()
