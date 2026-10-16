import json
from collections.abc import Collection
from typing import Any

import pandas as pd

from llm_workbench import db, formatting


def get_all_categories(
        data_source: pd.DataFrame | None = None,
) -> list[str]:
    # categories belong to prompts, so all of them are used by default
    if data_source is None:
        data_source = _prepare_prompt_table(db.prompts.get_all_prompts())

    if data_source.empty:
        return []

    return data_source["categories"].explode().dropna().unique().tolist()


def get_all_interactions(fill_null: bool = False) -> pd.DataFrame:
    df = pd.DataFrame(db.interactions.get_all_interactions())

    if df.empty:
        return df

    # parse categories from json array format
    df["categories"] = df["categories"].apply(formatting.parse_categories_from_json)

    # convert timestamps and duration to `datetime` type
    df["time"] = pd.to_datetime(df["time"])
    df["duration"] = pd.to_timedelta(df["duration"])

    # fill nan values from database (<NULL>) if needed
    if fill_null:
        df["system_prompt"] = df["system_prompt"].fillna("")

    return df


def _prepare_prompt_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["categories"] = df["categories"].apply(formatting.parse_categories_from_json)
    df["created_at"] = pd.to_datetime(df["created_at"])

    if "last_run_at" in df:
        df["last_run_at"] = pd.to_datetime(df["last_run_at"])

    return df


def get_prompt_overview() -> pd.DataFrame:
    return _prepare_prompt_table(db.prompts.get_prompt_overview())


def search_prompts(prompt_table: pd.DataFrame, search: str | None) -> pd.DataFrame:
    # case-insensitive search in the title, prompt and system prompt
    search = (search or "").strip()

    if not search or prompt_table.empty:
        return prompt_table

    searched_text = (
        prompt_table[["title", "prompt", "system_prompt"]]
        .fillna("")
        .astype(str)
        .agg("\n".join, axis=1)
    )
    matches = searched_text.str.contains(search, case=False, regex=False)

    return prompt_table.loc[matches].reset_index(drop=True)


def get_interaction_by_id(entry_id: int) -> dict[str, Any] | None:
    prompt_data = db.interactions.get_interaction_by_id(entry_id)

    if not prompt_data:
        return None

    prompt_data = prompt_data[0]
    categories = prompt_data.get("categories")

    if not categories:
        return prompt_data

    prompt_data["categories"] = formatting.parse_categories_from_json(categories)
    return prompt_data


def get_prompt_interactions(prompt_id: int) -> list[dict[str, Any]]:
    # every interaction of the prompt together with its judge results
    judge_results_by_interaction: dict[int, list[dict[str, Any]]] = {}
    for judge_result in db.judges.get_judge_results_by_prompt(prompt_id):
        judge_results_by_interaction.setdefault(judge_result["interaction_id"], []).append(judge_result)

    return [
        {
            "interaction": interaction,
            "judge_results": sorted(
                judge_results_by_interaction.get(interaction["id"], []),
                key=lambda judge_result: judge_result["label"] or "",
            ),
        }
        for interaction in db.interactions.get_interactions_by_prompt(prompt_id)
    ]


def summarize_runs(prompt_interactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # runs in the order of their first interaction, numbered from 1 within the prompt
    runs: dict[str, dict[str, Any]] = {}

    for interaction_object in sorted(prompt_interactions, key=lambda i: i["interaction"]["time"]):
        interaction = interaction_object["interaction"]
        run = runs.setdefault(interaction["run_id"], {
            "run_id": interaction["run_id"],
            "number": len(runs) + 1,
            "started_at": interaction["time"],
            "interaction_count": 0,
        })
        run["interaction_count"] += 1

    return list(runs.values())


def filter_prompt_interactions(
        prompt_interactions: list[dict[str, Any]],
        run_id: str | None = None,
        models: Collection[str] = (),
        manual_labels: Collection[str | None] = (),
) -> list[dict[str, Any]]:
    # an empty filter keeps all interactions, a None manual label selects unlabeled ones
    return [
        interaction_object
        for interaction_object in prompt_interactions
        if (run_id is None or interaction_object["interaction"]["run_id"] == run_id)
        and (not models or interaction_object["interaction"]["model"] in models)
        and (not manual_labels or interaction_object["interaction"]["manual_label"] in manual_labels)
    ]


def get_all_presets(fill_null: bool = False) -> pd.DataFrame:
    df = pd.DataFrame(db.presets.get_all_presets())

    if df.empty:
        return df

    df["categories"] = df["categories"].apply(formatting.parse_categories_from_json)

    # fill nan values from database (<NULL>) if needed
    if fill_null:
        df["system_prompt"] = df["system_prompt"].fillna("")

    return df


def save_prompt(
        prompt: str | None,
        system_prompt: str | None,
        categories: list[str] | None,
) -> int:
    # returns the id of the matching prompt, creating it if it doesn't exist yet
    prompt = formatting.normalize_prompt_text(prompt)

    if not prompt:
        raise ValueError("The prompt must not be empty.")

    return db.prompts.upsert_prompt(
        prompt,
        formatting.normalize_prompt_text(system_prompt),
        formatting.categories_to_json(categories),
    )


def add_preset(
        system_prompt: str | None,
        prompt: str,
        categories,
) -> int:
    # checks if such preset already exists, and if so, returns its existing id
    categories = json.dumps(categories, ensure_ascii=False)
    system_prompt = system_prompt or None

    matching_preset = db.presets.get_preset_id_by_content(prompt, system_prompt, categories)

    if matching_preset:
        return matching_preset
    else:
        return db.presets.insert_preset({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "categories": categories,
        })
