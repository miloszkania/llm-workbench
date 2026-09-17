import json
import re
import time
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from openrouter import components

from src import database, openrouter_api, judge
from src.errors import OpenRouterRequestError, ModelResponseError


###### UTILS

def page_config(name: str | None = None) -> None:
    st.set_page_config(
        layout="wide",
        page_title=f"{name} | LLM Workbench" if name else "LLM Workbench"
    )


def parse_categories_from_json(
        text: str | float | None,
) -> list[str] | None:
    if not isinstance(text, str) or not text or text == "[]":
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [text]


def get_all_categories(
        history_entries: pd.DataFrame | None = None,
) -> list[str]:
    data_source = history_entries

    if data_source is None:
        data_source = get_all_interactions()

    if data_source.empty:
        return []

    return data_source["categories"].explode().dropna().unique().tolist()


def remove_timestamp_from_model_id(model_id: str) -> str:
    # removes the snapshot of the model
    return re.sub(r"-\d{8}", "", model_id)


def format_timestamp(value: str) -> str:
    timestamp = datetime.fromisoformat(value)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(value: str) -> str:
    point_position = value.find(".")

    if point_position >= 0: # if there is no dot in value, point_position = -1
        value = value[:value.find(".")]

    hours, minutes, seconds = map(int, value.split(":"))

    # choose the suitable display option
    if minutes == 0:
        return f"{seconds} seconds"
    elif hours == 0:
        return f"{minutes} minutes{f' and {seconds} seconds' if seconds != 0 else ''}"
    else:
        return value


def format_model_price(
        raw_price: str,
        markdown: bool = False,
) -> str:
    price = float(raw_price)

    if markdown:
        return f"\\${(price * 1_000_000):,.2f}" if price >= 0 else "Varies by model"
    else:
        return f"{(price * 1_000_000):,.2f} $" if price >= 0 else "Varies by model"


###### HISTORY

def get_all_interactions(fill_null: bool = False) -> pd.DataFrame:
    df = pd.DataFrame(database.get_all_interactions())

    if df.empty:
        return df

    # parse categories from json array format
    df["categories"] = df["categories"].apply(parse_categories_from_json)

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

    prompt_data["categories"] = parse_categories_from_json(categories)
    return prompt_data


###### PRESETS

def get_all_presets(fill_null: bool = False) -> pd.DataFrame:
    df = pd.DataFrame(database.get_all_presets())

    if df.empty:
        return df

    df["categories"] = df["categories"].apply(parse_categories_from_json)

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
) -> tuple[
    list[int],
    list[OpenRouterRequestError | ModelResponseError],
    list[dict[str, Any]],
]:
    # store all ids of the interactions
    interaction_ids = []
    failed_judgments = []
    failed_interactions = []

    # send the prompt `repetition_count` times
    for i in range(repetition_count):
        # timeout of 3 seconds (if not first prompt of the batch)
        if i > 0: time.sleep(3.2)

        # send the prompt and receive a response
        try:
            response, start_timestamp, duration = openrouter_api.send_prompt(
                model, prompt, system_prompt, conversation_type="target"
            )
            response_content = openrouter_api.extract_response_text(response)
        except (OpenRouterRequestError, ModelResponseError) as error:
            failed_interactions.append(error)
            continue

        # clear the model id (remove the timestamp-snapshot)
        used_model = remove_timestamp_from_model_id(response.model)

        # add the prompt to database
        interaction_id = database.insert_interaction({
            "time": str(start_timestamp),
            "model": used_model,
            "prompt": prompt,
            "system_prompt": system_prompt if system_prompt else None,
            "categories": json.dumps(categories, ensure_ascii=False) if categories else None,
            "response": response_content,
            "duration": str(duration),
            "token_usage": response.usage.total_tokens,
            "price": response.usage.cost,
        })

        # get llm-as-a-judge classification
        current_failed_judgments = judge.evaluate_and_store_interaction(
            interaction_id, system_prompt, prompt, response_content, judge_config, judge_models
        )

        # save the failed judgments to display them in the next view
        failed_judgments.extend(current_failed_judgments)

        # save the id of the resulting interaction in the array
        interaction_ids.append(interaction_id)

    return interaction_ids, failed_interactions, failed_judgments


###### MODELS

def is_free_model(model_id: str) -> bool:
    return model_id == "openrouter/free" or model_id.endswith(":free")


@st.cache_data(ttl="1h", show_spinner="Loading available models…")
def get_models(
        sort: str = "most-popular",
        model_filter: str = "All",
) -> list[components.Model]:
    models = openrouter_api.get_model_list(sort)

    # Get the deserved models
    if model_filter == "Free":
        models = [i for i in models if is_free_model(i.id)]
    elif model_filter == "Paid":
        models = [i for i in models if not is_free_model(i.id)]

    return models


@st.cache_data(ttl="1h", show_spinner="Loading model information…")
def get_model_object(model_id: str) -> components.ModelResponse:
    return openrouter_api.get_model_object(model_id)
