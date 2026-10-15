import unittest

from llm_workbench import formatting


class CategoryParsingTests(unittest.TestCase):
    def test_json_array_is_parsed_to_list(self) -> None:
        self.assertEqual(formatting.parse_categories_from_json('["a", "b"]'), ["a", "b"])

    def test_empty_values_return_none(self) -> None:
        for value in (None, "", "[]", float("nan")):
            with self.subTest(value=value):
                self.assertIsNone(formatting.parse_categories_from_json(value))

    def test_invalid_json_is_wrapped_in_list(self) -> None:
        self.assertEqual(formatting.parse_categories_from_json("abc"), ["abc"])


class ModelIdTests(unittest.TestCase):
    def test_snapshot_date_is_removed(self) -> None:
        self.assertEqual(formatting.remove_timestamp_from_model_id("anthropic/claude-x-20250929"), "anthropic/claude-x")

    def test_snapshot_date_before_variant_is_removed(self) -> None:
        self.assertEqual(formatting.remove_timestamp_from_model_id("a/b-20250929:free"), "a/b:free")

    def test_plain_id_is_unchanged(self) -> None:
        self.assertEqual(formatting.remove_timestamp_from_model_id("openai/gpt-4o"), "openai/gpt-4o")

    def test_is_free_model(self) -> None:
        self.assertTrue(formatting.is_free_model("openrouter/free"))
        self.assertTrue(formatting.is_free_model("x/y:free"))
        self.assertFalse(formatting.is_free_model("x/y"))


class DurationAndTimestampTests(unittest.TestCase):
    def test_format_duration(self) -> None:
        cases = {
            "0:00:05.123": "5 seconds",
            "0:02:00": "2 minutes",
            "0:02:03": "2 minutes and 3 seconds",
            "1:02:03": "1:02:03",
            "1:00:05": "1:00:05",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(formatting.format_duration(value), expected)

    def test_format_timestamp_drops_microseconds(self) -> None:
        self.assertEqual(formatting.format_timestamp("2026-09-20 10:00:00.123456"), "2026-09-20 10:00:00")


class PriceTests(unittest.TestCase):
    def test_price_is_scaled_per_million_tokens(self) -> None:
        self.assertEqual(formatting.format_model_price("0.000001"), "1.00 $")

    def test_markdown_price_escapes_dollar(self) -> None:
        self.assertEqual(formatting.format_model_price("0.000001", markdown=True), "\\$1.00")

    def test_negative_price_varies_by_model(self) -> None:
        self.assertEqual(formatting.format_model_price("-1"), "Varies by model")
        self.assertEqual(formatting.format_model_price("-1", markdown=True), "Varies by model")


if __name__ == "__main__":
    unittest.main()
