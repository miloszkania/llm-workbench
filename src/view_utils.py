import json
import re
import time
from datetime import datetime

import openrouter.errors.toomanyrequestsresponse_error
import pandas as pd
import streamlit as st

from src import database, openrouter_api, judge

###### UTILS

def page_config(name=None):
    st.set_page_config(
        layout="wide",
        page_title=f"{name} | LLM Workbench" if name else "LLM Workbench"
    )


def unparse_categories_from_json(text):
    if not text or not isinstance(text, str) or text == "[]":
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [text]


def get_all_categories(history_entries: pd.DataFrame = None):
    data_source = history_entries

    if data_source is None:
        data_source = get_all_history_entries()

    if data_source.empty:
        return []

    return data_source["categories"].explode().dropna().unique().tolist()


# removes the snapshot of the model
def remove_timestamp_from_model_id(model_id):
    return re.sub(r"-\d{8}", "", model_id)


def format_timestamp(value):
    timestamp = datetime.fromisoformat(value)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(value):
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


###### HISTORY

def get_all_history_entries(fill_null=False):
    df = pd.DataFrame(database.get_all_interactions())

    if df.empty:
        return df

    # parse categories from json array format
    df["categories"] = df["categories"].apply(unparse_categories_from_json)

    # convert timestamps and duration to `datetime` type
    df["time"] = pd.to_datetime(df["time"])
    df["duration"] = pd.to_timedelta(df["duration"])

    # fill nan values from database (<NULL>) if needed
    if fill_null:
        df["system_prompt"] = df["system_prompt"].fillna("")

    return df


def get_single_history_entry(entry_id):
    prompt_data = database.get_interaction_by_id(int(entry_id))

    if not prompt_data:
        return None

    prompt_data = prompt_data[0]
    categories = prompt_data.get("categories")

    if not categories:
        return prompt_data

    prompt_data["categories"] = unparse_categories_from_json(categories)
    return prompt_data


###### PRESETS

def get_all_preset_entries(fill_null=False):
    df = pd.DataFrame(database.get_all_presets())

    if df.empty:
        return df

    df["categories"] = df["categories"].apply(unparse_categories_from_json)

    # fill nan values from database (<NULL>) if needed
    if fill_null:
        df["system_prompt"] = df["system_prompt"].fillna("")

    return df


def add_preset(system_prompt, prompt, categories):
    # check if such preset already exists, and if so, return its existing id
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
        model, system_prompt, prompt, categories, judge_config, judge_models, repetition_count=1
):
    # store all ids of the interactions
    interaction_ids = []

    # send the prompt `repetition_count` times
    for i in range(repetition_count):
        repeated_error_count = 0
        # try sending until there are no errors
        while True:
            try:
                response, start_timestamp, duration = openrouter_api.send_prompt(model, prompt, system_prompt)
                if len(response.choices) > 0:
                    response_content = response.choices[0].message.content
                else:
                    response_content = None

                # clear the model id (remove the timestamp-snapshot)
                used_model = remove_timestamp_from_model_id(response.model)

                # add the prompt to database
                interaction_id = database.insert_prompt_record({
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
                judge.evaluate_and_store_interaction(interaction_id, system_prompt, prompt, response_content,
                                                     judge_config, judge_models)

                # save the id of the resulting interaction in the array
                interaction_ids.append(interaction_id)

                # timeout of 3 seconds (if not last prompt of the batch)
                if i != repetition_count - 1:
                    time.sleep(3.2)

                break # breaking the try-until-succeeded loop
            except openrouter.errors.openroutererror.OpenRouterError as e:
                repeated_error_count += 1

                if repeated_error_count >= 3:
                    st.error(f"Repeated OpenRouter error: {e}. Try again later.")
                    return

                time.sleep(3.2)
                continue # try again

    # redirect to the prompt/batch details page
    param_string = ",".join(map(str, interaction_ids)) # parse [1, 2, 3, 4] into 1,2,3,4
    st.switch_page("pages/experiment_results.py", query_params={"id": param_string})


###### MODELS

@st.cache_data(ttl="1h", show_spinner="Loading available models…")
def get_model_ids(sort="most-popular", only_free_models=False):
    model_ids = [i.id for i in openrouter_api.get_model_list(sort)]

    # Get the deserved model ids
    if only_free_models:
        model_ids = [i for i in model_ids if i.endswith("free")]

    return model_ids
