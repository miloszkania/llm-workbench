import time

from src import database, openrouter_api, view_utils


def get_configuration_details(judge_config_id):
    fetched_object = [dict(i) for i in database.get_judge_configuration_by_id(judge_config_id)]

    if len(fetched_object) > 0: # should only have 0 or 1 element
        instructions = fetched_object[0].get("judge_prompt")
        explanation = fetched_object[0].get("require_explanation") == 1
        return instructions, explanation
    else:
        return None, None


def compose_judge_prompt(judge_instructions, system_prompt, prompt, response):
    # don't include the system_prompt if it doesn't exist
    if system_prompt:
        prompt_replacement = f"{system_prompt} {prompt}"
    else:
        prompt_replacement = prompt

    # in case of the instructions containing [PROMPT] or [RESPONSE] more than once,
    # or the prompt itself containing [RESPONSE], replace only the first occurrence or [PROMPT] and [RESPONSE]
    # of the instructions
    if judge_instructions.index("[PROMPT]") < judge_instructions.index("[RESPONSE]"):
        before_prompt, after_prompt = judge_instructions.split("[PROMPT]", maxsplit=1)
        after_prompt_before_response, after_response = after_prompt.split("[RESPONSE]", maxsplit=1)

        return f"{before_prompt}{prompt_replacement}{after_prompt_before_response}{response}{after_response}"
    else:
        before_response, after_response = judge_instructions.split("[RESPONSE]", maxsplit=1)
        after_response_before_prompt, after_prompt = after_response.split("[PROMPT]", maxsplit=1)

        return f"{before_response}{response}{after_response_before_prompt}{prompt_replacement}{after_prompt}"


def get_judge_result(judge_prompt, judge_model, require_explanation):
    judge_response, time, duration = openrouter_api.send_prompt(judge_model, judge_prompt, None)
    judge_message = judge_response.choices[0].message.content.strip()

    if require_explanation:
        label, explanation = judge_message.split(", Explanation: ", maxsplit=1)
    else:
        label, explanation = judge_message, None

    # check if judge sent a correct label
    if label not in ["success", "refusal", "unclear"]:
        label = None
        explanation = judge_message # save the whole response for debugging purposes

    return {
        "judge_model": view_utils.remove_timestamp_from_model_id(judge_response.model),
        "label": label,
        "explanation": explanation,
        "time": time,
        "duration": duration,
        "price": judge_response.usage.cost,
    }


def evaluate_and_store_interaction(interaction_id, system_prompt, prompt, response, judge_config_id, judge_models):
    if not judge_config_id or not judge_models:
        return

    judge_instructions, require_explanation = get_configuration_details(judge_config_id)

    if not judge_instructions:
        return

    judge_prompt = compose_judge_prompt(judge_instructions, system_prompt, prompt, response)

    for i in range(len(judge_models)):
        judge_model = judge_models[i]

        if i > 0: time.sleep(3.2)
        judge_result = get_judge_result(judge_prompt, judge_model, require_explanation)

        # we received an incorrect label from the judge - go to the next one
        if not judge_result.get("label"):
            continue

        # save the judge result into the database
        database.insert_judge_result({
            "interaction_id": interaction_id,
            "judge_config_id": judge_config_id,
            "judge_model": judge_result["judge_model"],
            "label": judge_result["label"],
            "explanation": judge_result["explanation"][:500] if require_explanation else None,
            "time": judge_result["time"],
            "duration": str(judge_result["duration"]),
            "price": judge_result["price"],
        })
