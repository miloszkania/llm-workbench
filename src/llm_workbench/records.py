import json
from typing import Any

import pandas as pd

from llm_workbench import db, formatting


def get_all_categories(
        history_entries: pd.DataFrame | None = None,
) -> list[str]:
    data_source = history_entries

    if data_source is None:
        data_source = get_all_interactions()

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
