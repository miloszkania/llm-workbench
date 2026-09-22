import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from src import database


LABELS = ("success", "refusal", "unclear")
LABEL_COUNT_COLUMNS = tuple(f"{label}_count" for label in LABELS)
JUDGE_SETUP_SEPARATOR = " · "

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


##### DATA PREPARATION

def _create_frame(
        records: Sequence[Mapping[str, Any]] | pd.DataFrame,
        columns: Sequence[str],
) -> pd.DataFrame:
    if isinstance(records, pd.DataFrame):
        frame = records.copy()
    else:
        frame = pd.DataFrame.from_records(records)

    # keep the expected columns even if the database result is empty
    return frame.reindex(columns=columns)


def _parse_categories(value: object) -> list[str]:
    if isinstance(value, list):
        return [category for category in value if isinstance(category, str) and category]

    if not isinstance(value, str) or not value or value == "[]":
        return []

    # categories are stored in the database as a json array
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        # keep old plain-text values as a single category
        return [value]

    if not isinstance(parsed_value, list):
        return [value]

    return [category for category in parsed_value if isinstance(category, str) and category]


def prepare_interactions(
        records: Sequence[Mapping[str, Any]] | pd.DataFrame,
) -> pd.DataFrame:
    interactions = _create_frame(records, INTERACTION_COLUMNS)

    # convert database values to the types used by analytics
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


##### DATA LOADING

def load_interactions() -> pd.DataFrame:
    return prepare_interactions(database.get_all_interactions())


def load_judge_results() -> pd.DataFrame:
    return prepare_judge_results(database.get_all_judge_results())


def load_presets() -> pd.DataFrame:
    return prepare_presets(database.get_all_presets())


##### FILTERS

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
        # include interactions that have at least one selected category
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


##### SHARED SUMMARIES

def get_latest_judge_results(judge_results: pd.DataFrame) -> pd.DataFrame:
    if judge_results.empty:
        return judge_results.copy()

    # if times are equal, use the database id to select the latest result
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

    # don't include uncategorized interactions as a chart category
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


def summarize_activity(interactions: pd.DataFrame) -> pd.DataFrame:
    dated_interactions = interactions.loc[interactions["time"].notna()].copy()

    if dated_interactions.empty:
        return pd.DataFrame(columns=["date", "interaction_count"])

    dated_interactions["date"] = dated_interactions["time"].dt.normalize()

    return (
        dated_interactions
        .groupby("date")
        .size()
        .rename("interaction_count")
        .reset_index()
        .sort_values("date")
        .reset_index(drop=True)
    )


def summarize_costs(
        interactions: pd.DataFrame,
        judge_results: pd.DataFrame,
) -> pd.DataFrame:
    target_costs = interactions.loc[interactions["time"].notna()].copy()
    target_costs["date"] = target_costs["time"].dt.normalize()
    target_costs = (
        target_costs
        .groupby("date", as_index=False)["price"]
        .sum()
        .rename(columns={"price": "target_cost"})
    )

    judging_costs = judge_results.loc[judge_results["time"].notna()].copy()
    judging_costs["date"] = judging_costs["time"].dt.normalize()
    judging_costs = (
        judging_costs
        .groupby("date", as_index=False)["price"]
        .sum()
        .rename(columns={"price": "judging_cost"})
    )

    # include dates that have target interactions or judge evaluations
    costs = target_costs.merge(judging_costs, on="date", how="outer")

    if costs.empty:
        return pd.DataFrame(columns=["date", "target_cost", "judging_cost", "total_cost"])

    costs[["target_cost", "judging_cost"]] = costs[["target_cost", "judging_cost"]].fillna(0.0)
    costs["total_cost"] = costs["target_cost"] + costs["judging_cost"]

    return costs.sort_values("date").reset_index(drop=True)


def get_manual_label_records(interactions: pd.DataFrame) -> pd.DataFrame:
    label_records = interactions.loc[
        interactions["manual_label"].isin(LABELS),
        ["id", "manual_label"],
    ]

    return (
        label_records
        .rename(columns={"id": "interaction_id", "manual_label": "label"})
        .reset_index(drop=True)
    )


def get_judge_label_records(judge_results: pd.DataFrame) -> pd.DataFrame:
    return (
        judge_results.loc[
            judge_results["label"].isin(LABELS),
            ["interaction_id", "label"],
        ]
        .reset_index(drop=True)
    )


def _add_label_metrics(
        summary: pd.DataFrame,
        labeled_groups: pd.DataFrame,
        group_columns: Sequence[str],
) -> pd.DataFrame:
    group_columns = list(group_columns)

    if labeled_groups.empty:
        # add zero counts if none of the groups have labels
        result = summary.copy()
        for column in LABEL_COUNT_COLUMNS:
            result[column] = 0
    else:
        # count every supported label separately for each group
        label_counts = (
            labeled_groups
            .groupby([*group_columns, "label"])
            .size()
            .unstack(fill_value=0)
            .reindex(columns=LABELS, fill_value=0)
            .rename(columns={label: f"{label}_count" for label in LABELS})
            .reset_index()
        )
        result = summary.merge(label_counts, on=group_columns, how="left")
        result[list(LABEL_COUNT_COLUMNS)] = (
            result[list(LABEL_COUNT_COLUMNS)]
            .fillna(0)
            .astype(int)
        )

    result["label_count"] = result[list(LABEL_COUNT_COLUMNS)].sum(axis=1)
    # leave the success share empty for groups without labels
    result["success_share"] = (
        result["success_count"]
        .div(result["label_count"])
        .mul(100)
        .where(result["label_count"].gt(0))
    )

    return result


##### MODEL AND CATEGORY ANALYTICS

def summarize_models(
        interactions: pd.DataFrame,
        label_records: pd.DataFrame,
) -> pd.DataFrame:
    model_data = interactions.loc[interactions["model"].notna()].copy()

    if model_data.empty:
        return pd.DataFrame(columns=[
            "model",
            "interaction_count",
            *LABEL_COUNT_COLUMNS,
            "label_count",
            "success_share",
            "median_duration_seconds",
            "median_tokens",
            "total_cost",
            "average_cost",
        ])

    model_data["duration_seconds"] = model_data["duration"].dt.total_seconds()
    summary = (
        model_data
        .groupby("model", as_index=False)
        .agg(
            interaction_count=("id", "size"),
            median_duration_seconds=("duration_seconds", "median"),
            median_tokens=("token_usage", "median"),
            total_cost=("price", lambda values: values.sum(min_count=1)),
            average_cost=("price", "mean"),
        )
    )
    # join labels separately, so repeated judge labels don't change interaction metrics
    labeled_models = label_records.merge(
        model_data[["id", "model"]],
        left_on="interaction_id",
        right_on="id",
        how="inner",
    )
    summary = _add_label_metrics(summary, labeled_models, ["model"])

    return (
        summary
        .sort_values(["interaction_count", "model"], ascending=[False, True])
        .reset_index(drop=True)
    )


def summarize_categories(
        interactions: pd.DataFrame,
        label_records: pd.DataFrame,
) -> pd.DataFrame:
    # one interaction can contribute once to each assigned category
    categorized = explode_categories(interactions)

    if categorized.empty:
        return pd.DataFrame(columns=[
            "category",
            "interaction_count",
            *LABEL_COUNT_COLUMNS,
            "label_count",
            "success_share",
        ])

    summary = (
        categorized
        .groupby("category", as_index=False)["id"]
        .nunique()
        .rename(columns={"id": "interaction_count"})
    )
    labeled_categories = label_records.merge(
        categorized[["id", "category"]],
        left_on="interaction_id",
        right_on="id",
        how="inner",
    )
    summary = _add_label_metrics(summary, labeled_categories, ["category"])

    return (
        summary
        .sort_values(["interaction_count", "category"], ascending=[False, True])
        .reset_index(drop=True)
    )


def summarize_model_categories(
        interactions: pd.DataFrame,
        label_records: pd.DataFrame,
) -> pd.DataFrame:
    # use one row for every model and assigned category pair
    categorized = explode_categories(interactions)

    if categorized.empty:
        return pd.DataFrame(columns=[
            "model",
            "category",
            "interaction_count",
            *LABEL_COUNT_COLUMNS,
            "label_count",
            "success_share",
        ])

    summary = (
        categorized
        .groupby(["model", "category"], as_index=False)["id"]
        .nunique()
        .rename(columns={"id": "interaction_count"})
    )
    labeled_groups = label_records.merge(
        categorized[["id", "model", "category"]],
        left_on="interaction_id",
        right_on="id",
        how="inner",
    )
    summary = _add_label_metrics(
        summary,
        labeled_groups,
        ["model", "category"],
    )

    return summary.sort_values(["model", "category"]).reset_index(drop=True)


##### JUDGE ANALYTICS

def _add_judge_setup(judge_results: pd.DataFrame) -> pd.DataFrame:
    # each model and configuration pair is a separate judge setup
    results = judge_results.loc[
        judge_results["judge_model"].notna()
        & judge_results["judge_config_id"].notna()
    ].copy()
    results["judge_setup"] = (
        results["judge_model"].astype(str)
        + JUDGE_SETUP_SEPARATOR
        + results["judge_config_id"].astype(str)
    )

    return results


def summarize_judges(judge_results: pd.DataFrame) -> pd.DataFrame:
    judge_data = _add_judge_setup(judge_results)

    if judge_data.empty:
        return pd.DataFrame(columns=[
            "judge_model",
            "judge_config_id",
            "judge_setup",
            "evaluation_count",
            "interaction_count",
            *LABEL_COUNT_COLUMNS,
            "label_count",
            "success_share",
            "median_duration_seconds",
            "total_cost",
            "average_cost",
        ])

    judge_data["duration_seconds"] = judge_data["duration"].dt.total_seconds()
    summary = (
        judge_data
        .groupby(["judge_model", "judge_config_id"], as_index=False)
        .agg(
            evaluation_count=("id", "size"),
            interaction_count=("interaction_id", "nunique"),
            median_duration_seconds=("duration_seconds", "median"),
            total_cost=("price", lambda values: values.sum(min_count=1)),
            average_cost=("price", "mean"),
        )
    )

    # use every evaluation for costs, but only the latest label for outcomes
    latest_results = _add_judge_setup(get_latest_judge_results(judge_data))
    valid_latest_results = latest_results.loc[
        latest_results["label"].isin(LABELS)
    ]
    summary = _add_label_metrics(
        summary,
        valid_latest_results,
        ["judge_model", "judge_config_id"],
    )
    summary["judge_setup"] = (
        summary["judge_model"].astype(str)
        + JUDGE_SETUP_SEPARATOR
        + summary["judge_config_id"].astype(str)
    )

    return (
        summary
        .sort_values(
            ["evaluation_count", "judge_model", "judge_config_id"],
            ascending=[False, True, True],
        )
        .reset_index(drop=True)
    )


def summarize_judge_agreement(judge_results: pd.DataFrame) -> pd.DataFrame:
    latest_results = _add_judge_setup(get_latest_judge_results(judge_results))
    valid_results = latest_results.loc[latest_results["label"].isin(LABELS)]

    if valid_results.empty:
        return pd.DataFrame(columns=[
            "judge_a",
            "judge_b",
            "overlap_count",
            "agreement_count",
            "agreement_share",
        ])

    # align labels by interaction before comparing every judge pair
    label_matrix = valid_results.pivot(
        index="interaction_id",
        columns="judge_setup",
        values="label",
    )
    agreement_rows = []

    for judge_a in label_matrix.columns:
        for judge_b in label_matrix.columns:
            paired_labels = pd.concat(
                [label_matrix[judge_a], label_matrix[judge_b]],
                axis=1,
                keys=["label_a", "label_b"],
            ).dropna()
            overlap_count = len(paired_labels)
            agreement_count = int(
                paired_labels["label_a"].eq(paired_labels["label_b"]).sum()
            )
            agreement_share = (
                agreement_count / overlap_count * 100
                if overlap_count > 0
                else None
            )
            agreement_rows.append({
                "judge_a": judge_a,
                "judge_b": judge_b,
                "overlap_count": overlap_count,
                "agreement_count": agreement_count,
                "agreement_share": agreement_share,
            })

    return pd.DataFrame(agreement_rows)


##### OVERVIEW

def get_overview_metrics(
        interactions: pd.DataFrame,
        judge_results: pd.DataFrame,
) -> OverviewMetrics:
    # count each category once across all filtered interactions
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
