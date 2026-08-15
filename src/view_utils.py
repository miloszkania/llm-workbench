import json
import re
import time

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
def clear_model_id(model_id):
    return re.sub(r"-\d{8}", "", model_id)


###### HISTORY

def get_all_history_entries(fill_null=False):
    df = pd.DataFrame(database.get_all_prompt_records())

    if df.empty:
        return df

    # parse categories from json array format
    df["categories"] = df["categories"].apply(unparse_categories_from_json)

    # convert timestamps and duration to `datetime` type
    df["time"] = pd.to_datetime(df["time"])
    df["duration"] = pd.to_timedelta(df["duration"])

    # fill nan values from database (<NULL>) if needed
    if fill_null:
        df["preset"] = df["preset"].fillna("")
        df["system_prompt"] = df["system_prompt"].fillna("")

    return df


def get_single_history_entry(entry_id):
    prompt_data = database.get_prompt_record(int(entry_id))

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
    preset_table = get_all_preset_entries(fill_null=True)

    if not preset_table.empty:
        matching_preset = preset_table.loc[
            (preset_table["system_prompt"] == system_prompt) &
            (preset_table["prompt"] == prompt)
        ]

        if not matching_preset.empty:
            preset_id = matching_preset.iloc[0]["id"].item() # .item() to parse from int64 to normal int
            return preset_id

        else:
            return database.insert_preset({
                "prompt": prompt,
                "system_prompt": system_prompt if system_prompt else None,
                "categories": json.dumps(categories, ensure_ascii=False)
            })
    else:
        return database.insert_preset({
            "prompt": prompt,
            "system_prompt": system_prompt if system_prompt else None,
            "categories": json.dumps(categories, ensure_ascii=False)
        })


###### PROMPTS

def send_prompt(model, system_prompt, prompt, categories, repetition_count=1):
    # find if the prompt matches any preset
    preset_table = get_all_preset_entries(fill_null=True)
    matching_preset = preset_table.loc[
        (preset_table.get("system_prompt") == system_prompt) &
        (preset_table["prompt"] == prompt)
    ]

    if not matching_preset.empty:
        preset = matching_preset.iloc[0]["id"].item()

        # if no categories were set manually, set them according to the matching preset
        if not categories:
            categories = matching_preset.iloc[0]["categories"]
    else:
        preset = None

    # store all ids of records in batch
    record_ids = []

    # send the prompt `repetition_count` times
    for i in range(repetition_count):
        repeated_error_count = 0
        # try sending until there are no errors
        while True:
            try:
                response, start_timestamp, duration = openrouter_api.send_prompt(model, prompt, system_prompt)
                response_content = response.choices[0].message.content

                # clear the model id (remove the timestamp-snapshot)
                model_used = clear_model_id(response.model)

                # add the prompt to database
                record_id = database.insert_prompt_record({
                    "time": str(start_timestamp),
                    "model": model_used,
                    "preset": preset,
                    "prompt": prompt,
                    "system_prompt": system_prompt if system_prompt else None,
                    "categories": json.dumps(categories, ensure_ascii=False) if categories else None,
                    "response": response_content,
                    "duration": str(duration),
                    "token_usage": response.usage.total_tokens
                })

                # get llm-as-a-judge classification
                judge.get_llm_judge_label(record_id, system_prompt, prompt, response_content)

                # save the prompt id
                record_ids.append(record_id)

                # timeout of 2 seconds (if not last prompt of the batch)
                if i != repetition_count - 1:
                    time.sleep(2)

                break
            except openrouter.errors.openroutererror.OpenRouterError as e:
                repeated_error_count += 1

                if repeated_error_count >= 3:
                    st.error(f"Repeated OpenRouter error: {e}. Try again later.")
                    return

                time.sleep(2)
                continue

    # parse [1, 2, 3, 4] into 1,2,3,4
    param_string = ",".join(map(str, record_ids))
    st.switch_page("pages/batch_details.py", query_params={"ids": param_string})



###### MODELS

@st.cache_data(ttl="1h")
def get_model_ids(sort="most-popular", only_free_models=False):
    model_ids = [i.id for i in openrouter_api.get_model_list(sort)]

    # Get the deserved model ids
    if only_free_models:
        model_ids = [i for i in model_ids if i.endswith("free")]

    return model_ids
