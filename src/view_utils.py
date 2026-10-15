import json
import re
import time
from datetime import datetime
from typing import Any, Callable

import pandas as pd
import streamlit as st
from openrouter import components

from src import database, formatting, openrouter_api, judge
from src.errors import OpenRouterRequestError, ModelResponseError


###### UTILS

def page_config(name: str | None = None) -> None:
    st.set_page_config(
        layout="wide",
        page_title=f"{name} | LLM Workbench" if name else "LLM Workbench"
    )


def get_all_categories(
        history_entries: pd.DataFrame | None = None,
) -> list[str]:
    data_source = history_entries

    if data_source is None:
        data_source = get_all_interactions()

    if data_source.empty:
        return []

    return data_source["categories"].explode().dropna().unique().tolist()


###### HISTORY

def get_all_interactions(fill_null: bool = False) -> pd.DataFrame:
    df = pd.DataFrame(database.get_all_interactions())

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
    prompt_data = database.get_interaction_by_id(entry_id)

    if not prompt_data:
        return None

    prompt_data = prompt_data[0]
    categories = prompt_data.get("categories")

    if not categories:
        return prompt_data

    prompt_data["categories"] = formatting.parse_categories_from_json(categories)
    return prompt_data


###### PRESETS

def get_all_presets(fill_null: bool = False) -> pd.DataFrame:
    df = pd.DataFrame(database.get_all_presets())

    if df.empty:
        return df

    df["categories"] = df["categories"].apply(formatting.parse_categories_from_json)

    # fill nan values from database (<NULL>) if needed
    if fill_null:
        df["system_prompt"] = df["system_prompt"].fillna("")

    return df


def add_preset(
        system_prompt: str | None,
        prompt: str,
        categories,
) -> int:
    # checks if such preset already exists, and if so, returns its existing id
    categories = json.dumps(categories, ensure_ascii=False)
    system_prompt = system_prompt or None

    matching_preset = database.get_preset_id_by_content(prompt, system_prompt, categories)

    if matching_preset:
        return matching_preset
    else:
        return database.insert_preset({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "categories": categories,
        })


###### PROMPTS

def generate_and_evaluate_interactions(
        model: str,
        system_prompt: str | None,
        prompt: str,
        categories: list[str],
        judge_config: str | None,
        judge_models: list[str] | None,
        repetition_count: int = 1,
        on_interaction_start: Callable[[int, int], None] | None = None,
        on_judgment_start: Callable[[int, int], None] | None = None,
) -> tuple[
    list[int],
    list[OpenRouterRequestError | ModelResponseError],
    list[dict[str, Any]],
]:
    # store all ids of the interactions
    interaction_ids = []
    failed_judgments = []
    interaction_errors = []

    # send the prompt `repetition_count` times
    for i in range(1, repetition_count + 1):
        # pause between requests (if not first prompt of the batch)
        if i > 1: time.sleep(openrouter_api.REQUEST_DELAY_S)

        # run the callback function to update the progress bar
        if on_interaction_start:
            on_interaction_start(i, repetition_count)

        # send the prompt and receive a response
        try:
            response, start_timestamp, duration = openrouter_api.send_prompt(
                model, prompt, system_prompt, conversation_type="target"
            )
            response_content = openrouter_api.extract_response_text(response)
        except (OpenRouterRequestError, ModelResponseError) as error:
            interaction_errors.append(error)
            continue

        # clear the model id (remove the timestamp-snapshot)
        used_model = formatting.remove_timestamp_from_model_id(response.model)
        token_usage, price = openrouter_api.extract_usage(response)

        # add the prompt to database
        interaction_id = database.insert_interaction({
            "time": str(start_timestamp),
            "model": used_model,
            "prompt": prompt,
            "system_prompt": system_prompt if system_prompt else None,
            "categories": json.dumps(categories, ensure_ascii=False) if categories else None,
            "response": response_content,
            "duration": str(duration),
            "token_usage": token_usage,
            "price": price,
        })

        # get llm-as-a-judge classification
        current_failed_judgments = judge.evaluate_and_store_interaction(
            interaction_id,
            system_prompt,
            prompt,
            response_content,
            judge_config,
            judge_models,
            on_judgment_start=on_judgment_start,
        )

        # save the failed judgments to display them in the next view
        failed_judgments.extend(current_failed_judgments)

        # save the id of the resulting interaction in the array
        interaction_ids.append(interaction_id)

    return interaction_ids, interaction_errors, failed_judgments


###### MODELS


@st.cache_data(ttl="1h", show_spinner="Loading available models…")
def get_models(
        sort: str = "most-popular",
        model_filter: str = "All",
) -> list[components.Model]:
    models = openrouter_api.get_model_list(sort)

    # Get the deserved models
    if model_filter == "Free":
        models = [i for i in models if formatting.is_free_model(i.id)]
    elif model_filter == "Paid":
        models = [i for i in models if not formatting.is_free_model(i.id)]

    return models


@st.cache_data(ttl="1h", show_spinner="Loading model information…")
def get_model_object(model_id: str) -> components.ModelResponse:
    return openrouter_api.get_model_object(model_id)
