import json
import time

import openrouter

from automator.prompt_generator import generate_all_prompts
from src import view_utils, database, judge, openrouter_api


def add_preset(system_prompt, prompt, categories):
    # check if such preset already exists
    preset_table = view_utils.get_all_preset_entries(fill_null=True)

    if not preset_table.empty:
        matching_preset = preset_table.loc[
            (preset_table["system_prompt"] == system_prompt) &
            (preset_table["prompt"] == prompt)
        ]

        if not matching_preset.empty:
            return

        else:
            database.insert_preset({
                "prompt": prompt,
                "system_prompt": system_prompt if system_prompt else None,
                "categories": json.dumps(categories, ensure_ascii=False)
            })
    else:
        database.insert_preset({
            "prompt": prompt,
            "system_prompt": system_prompt if system_prompt else None,
            "categories": json.dumps(categories, ensure_ascii=False)
        })




def send_prompt(model, system_prompt, prompt, categories, repetition_count):
    # find if the prompt matches any preset
    preset_table = view_utils.get_all_preset_entries(fill_null=True)

    matching_preset = preset_table.loc[
        (preset_table["system_prompt"] == system_prompt) &
        (preset_table["prompt"] == prompt)
    ]

    if not matching_preset.empty:
        preset = matching_preset.iloc[0]["id"].item()

        # if no categories were set manually, set them according to the matching preset
        if not categories:
            categories = matching_preset.iloc[0]["categories"]
    else:
        preset = None


    # send the prompt `repetition_count` times
    for i in range(repetition_count):
        repeated_error_count = 0
        # try sending until there are no errors
        while True:
            try:
                response, start_timestamp, duration = openrouter_api.send_prompt(model, prompt, system_prompt)
                response_content = response.choices[0].message.content

                # clear the model id (remove the timestamp-snapshot)
                model_used = view_utils.clear_model_id(response.model)

                # add the prompt to database
                record_id = database.insert_prompt_record({
                    "time": str(start_timestamp),
                    "model": model_used,
                    "preset_id": preset,
                    "prompt": prompt,
                    "system_prompt": system_prompt if system_prompt else None,
                    "categories": json.dumps(categories, ensure_ascii=False) if categories else None,
                    "response": response_content,
                    "duration": str(duration),
                    "token_usage": response.usage.total_tokens,
                    "price": response.usage.cost,
                })

                # get llm-as-a-judge classification
                judge.get_llm_judge_label(record_id, system_prompt, prompt, response_content)

                # timeout of 2 seconds (if not last prompt of the batch)
                if i != repetition_count - 1:
                    time.sleep(2)

                break
            except openrouter.errors.openroutererror.OpenRouterError as e:
                repeated_error_count += 1

                if repeated_error_count >= 3:
                    print(f"Repeated OpenRouter error: {e}. Try again later.")
                    raise e
                    return

                time.sleep(2)
                continue


PREFERRED_CATEGORY = None

USED_MODELS = [
    # "google/gemma-4-31b-it",
    # "meta-llama/llama-3.2-3b-instruct",
    # "meta-llama/llama-3.3-70b-instruct",
    # "openai/gpt-oss-20b",
    # "openai/gpt-oss-120b",
    # "qwen/qwen3-next-80b-a3b-instruct",
    "nousresearch/hermes-4-70b",
]

USED_PROMPTS = generate_all_prompts(PREFERRED_CATEGORY)

START_PROMPT = 1

current_cnt = 0
success_cnt = 0
for prompt in USED_PROMPTS:
    categories = prompt.get("categories")
    content = prompt.get("content")

    current_cnt += 1
    if current_cnt < START_PROMPT:
        print(f"Prompt {current_cnt}/{len(USED_PROMPTS)} {categories}: skipped")
        continue
    else:
        print(f"Prompt {current_cnt}/{len(USED_PROMPTS)} {categories}:")

    for model in USED_MODELS:
        print(f" - {model}: ", end="")
        for i in range(7): # trying every prompt 7 times for every model
            try:
                add_preset("", content, categories)
                send_prompt(model, "", content, categories, 3)
                print("✅ ", end="")
                success_cnt += 1
                break
            except openrouter.errors.toomanyrequestsresponse_error.TooManyRequestsResponseError:
                print("❌RL ", end="")
                # print("ERROR: Too many requests - rate limited by OpenRouter. Try again later.")
                time.sleep(2)
            except openrouter.errors.openroutererror.OpenRouterError as e:
                if "flagged" in e:
                    print("❌FL ", end="")
                    # print(f"ERROR: The request to {model} was flagged by OpenInterface. Try again with a different model.")
                else:
                    print("❌ER ", end="")
                    # print(f"ERROR: OpenRouter error: {e}. Try again later.")
                time.sleep(2)
        print()

print(f"Done, {success_cnt}/{current_cnt} sends succeeded")