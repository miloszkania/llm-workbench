import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from src import database


LABELS = ("success", "refusal", "unclear")

INTERACTION_COLUMNS = (
    "id",
    "time",
    "model",
    "prompt",
    "system_prompt",
    "categories",
    "response",
    "manual_label",
    "duration",
    "token_usage",
    "price",
)

JUDGE_RESULT_COLUMNS = (
    "id",
    "interaction_id",
    "judge_config_id",
    "judge_model",
    "label",
    "explanation",
    "time",
    "duration",
    "price",
)

PRESET_COLUMNS = (
    "id",
    "prompt",
    "system_prompt",
    "categories",
    "created_at",
)


@dataclass(frozen=True)
class OverviewMetrics:
    interaction_count: int
    target_model_count: int
    category_count: int
    categorized_interaction_count: int
    manually_labeled_interaction_count: int
    judged_interaction_count: int
    judgment_count: int
    target_cost: float
    judging_cost: float
    token_usage: int
    median_duration_seconds: float | None


def _create_frame(
        records: Sequence[Mapping[str, Any]] | pd.DataFrame,
        columns: Sequence[str],
) -> pd.DataFrame:
    if isinstance(records, pd.DataFrame):
        frame = records.copy()
    else:
        frame = pd.DataFrame.from_records(records)

    # keep stable schemas so empty database results need no special handling in the UI
    return frame.reindex(columns=columns)


def _parse_categories(value: object) -> list[str]:
    if isinstance(value, list):
        return [category for category in value if isinstance(category, str) and category]

    if not isinstance(value, str) or not value or value == "[]":
        return []

    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        return [value]

    if not isinstance(parsed_value, list):
        return [value]

    return [category for category in parsed_value if isinstance(category, str) and category]


def prepare_interactions(
        records: Sequence[Mapping[str, Any]] | pd.DataFrame,
) -> pd.DataFrame:
    interactions = _create_frame(records, INTERACTION_COLUMNS)

    # parse database values once before filtering and aggregating them
    interactions["categories"] = interactions["categories"].apply(_parse_categories)
    interactions["time"] = pd.to_datetime(interactions["time"], errors="coerce")
    interactions["duration"] = pd.to_timedelta(interactions["duration"], errors="coerce")
    interactions["token_usage"] = pd.to_numeric(interactions["token_usage"], errors="coerce")
    interactions["price"] = pd.to_numeric(interactions["price"], errors="coerce")

    return interactions


def prepare_judge_results(
        records: Sequence[Mapping[str, Any]] | pd.DataFrame,
) -> pd.DataFrame:
    judge_results = _create_frame(records, JUDGE_RESULT_COLUMNS)

    judge_results["time"] = pd.to_datetime(judge_results["time"], errors="coerce")
    judge_results["duration"] = pd.to_timedelta(judge_results["duration"], errors="coerce")
    judge_results["price"] = pd.to_numeric(judge_results["price"], errors="coerce")

    return judge_results


def prepare_presets(
        records: Sequence[Mapping[str, Any]] | pd.DataFrame,
) -> pd.DataFrame:
    presets = _create_frame(records, PRESET_COLUMNS)

    presets["categories"] = presets["categories"].apply(_parse_categories)
    presets["created_at"] = pd.to_datetime(presets["created_at"], errors="coerce")

    return presets


def load_interactions() -> pd.DataFrame:
    return prepare_interactions(database.get_all_interactions())


def load_judge_results() -> pd.DataFrame:
    return prepare_judge_results(database.get_all_judge_results())


def load_presets() -> pd.DataFrame:
    return prepare_presets(database.get_all_presets())


def filter_interactions(
        interactions: pd.DataFrame,
        start_date: date | None = None,
        end_date: date | None = None,
        models: Sequence[str] | None = None,
        categories: Sequence[str] | None = None,
) -> pd.DataFrame:
    if start_date and end_date and start_date > end_date:
        raise ValueError("The start date cannot be later than the end date.")

    filtered = interactions.copy()

    if start_date:
        filtered = filtered.loc[filtered["time"].dt.date >= start_date]

    if end_date:
        filtered = filtered.loc[filtered["time"].dt.date <= end_date]

    if models is not None:
        filtered = filtered.loc[filtered["model"].isin(models)]

    if categories is not None:
        selected_categories = set(categories)
        filtered = filtered.loc[
            filtered["categories"].apply(
                lambda assigned: bool(selected_categories.intersection(assigned))
            )
        ]

    return filtered.reset_index(drop=True)


def filter_judge_results(
        judge_results: pd.DataFrame,
        interaction_ids: Sequence[int] | None = None,
        judge_config_ids: Sequence[str] | None = None,
        judge_models: Sequence[str] | None = None,
) -> pd.DataFrame:
    filtered = judge_results.copy()

    if interaction_ids is not None:
        filtered = filtered.loc[filtered["interaction_id"].isin(interaction_ids)]

    if judge_config_ids is not None:
        filtered = filtered.loc[filtered["judge_config_id"].isin(judge_config_ids)]

    if judge_models is not None:
        filtered = filtered.loc[filtered["judge_model"].isin(judge_models)]

    return filtered.reset_index(drop=True)


def get_latest_judge_results(judge_results: pd.DataFrame) -> pd.DataFrame:
    if judge_results.empty:
        return judge_results.copy()

    # use the row id as a stable tie-breaker when two results have the same timestamp
    sorted_results = judge_results.sort_values(
        by=["time", "id"],
        na_position="first",
    )

    return (
        sorted_results
        .drop_duplicates(
            subset=["interaction_id", "judge_config_id", "judge_model"],
            keep="last",
        )
        .sort_values(by="id")
        .reset_index(drop=True)
    )


def explode_categories(interactions: pd.DataFrame) -> pd.DataFrame:
    exploded = interactions.copy().explode("categories")
    exploded = exploded.rename(columns={"categories": "category"})

    # uncategorized interactions are measured separately and do not form a chart category
    return exploded.loc[exploded["category"].notna() & exploded["category"].ne("")].reset_index(drop=True)


def summarize_labels(labels: pd.Series) -> pd.DataFrame:
    counts = labels.loc[labels.isin(LABELS)].value_counts()
    counts = counts.reindex(LABELS, fill_value=0)
    total = int(counts.sum())

    distribution = counts.rename_axis("label").reset_index(name="count")
    distribution["percentage"] = (
        distribution["count"] / total * 100 if total > 0 else 0.0
    )

    return distribution


def get_overview_metrics(
        interactions: pd.DataFrame,
        judge_results: pd.DataFrame,
) -> OverviewMetrics:
    category_values = {
        category
        for assigned_categories in interactions["categories"]
        for category in assigned_categories
    }

    duration_median = interactions["duration"].median()
    median_duration_seconds = (
        None if pd.isna(duration_median) else duration_median.total_seconds()
    )

    return OverviewMetrics(
        interaction_count=len(interactions),
        target_model_count=interactions["model"].nunique(),
        category_count=len(category_values),
        categorized_interaction_count=int(interactions["categories"].apply(bool).sum()),
        manually_labeled_interaction_count=int(interactions["manual_label"].isin(LABELS).sum()),
        judged_interaction_count=judge_results["interaction_id"].nunique(),
        judgment_count=len(judge_results),
        target_cost=float(interactions["price"].sum()),
        judging_cost=float(judge_results["price"].sum()),
        token_usage=int(interactions["token_usage"].sum()),
        median_duration_seconds=median_duration_seconds,
    )
