import re
import time
from collections.abc import Callable
from typing import Any

from llm_workbench import db, formatting
from llm_workbench.errors import ModelResponseError, OpenRouterRequestError
from llm_workbench.llm import openrouter_api


def get_configuration_details(
    judge_config_id: str,
) -> tuple[str | None, bool]:
    judge_config = db.judges.get_judge_configuration_by_id(judge_config_id)

    if judge_config is None:
        return None, False

    return judge_config["judge_prompt"], judge_config["require_explanation"] == 1


def compose_judge_prompt(
    judge_instructions: str,
    system_prompt: str | None,
    prompt: str,
    response: str,
) -> str:
    # label both parts if there is a system prompt, so the judge can tell the instructions apart from the request
    if system_prompt:
        prompt_replacement = f"System prompt:\n{system_prompt}\n\nUser prompt:\n{prompt}"
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


def get_judge_result(
    judge_prompt: str,
    judge_model: str,
    require_explanation: bool,
) -> dict[str, Any]:
    judge_response, time, duration = openrouter_api.send_prompt(
        model=judge_model,
        prompt=judge_prompt,
        system_prompt=None,
        conversation_type="judge",
    )
    judge_message = openrouter_api.extract_response_text(judge_response)
    used_model = formatting.remove_timestamp_from_model_id(judge_response.model)
    _, price = openrouter_api.extract_usage(judge_response)

    # parse the judge response
    if require_explanation:
        # check if the response has the right format.
        # we accept both lowercase and uppercase, more than one space or no comma before "Explanation"
        match = re.fullmatch(
            pattern=r"\W*(success|refusal|unclear)\W*Explanation\s*:\s*(.+?)\s*",
            string=judge_message,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            label, explanation = match.groups()
        else:
            label = None
            explanation = judge_message

    else:
        # like above, punctuation or markdown around the label is accepted (e.g. "Refusal." or "**success**")
        match = re.fullmatch(
            pattern=r"\W*(success|refusal|unclear)\W*",
            string=judge_message,
            flags=re.IGNORECASE,
        )
        label = match.group(1) if match else judge_message
        explanation = None

    # normalize the label
    label = label.strip().lower() if label else None

    # check if judge sent a correct label
    if label not in ["success", "refusal", "unclear"]:
        raise ModelResponseError(
            message=(f"The judge returned an incorrectly formatted response. Raw response: {judge_message}"),
            model=used_model,
        )

    return {
        "judge_model": used_model,
        "label": label,
        "explanation": explanation,
        "time": time,
        "duration": duration,
        "price": price,
    }


def evaluate_and_store_interaction(
    interaction_id: int,
    system_prompt: str | None,
    prompt: str,
    response: str,
    judge_config_id: str | None,
    judge_models: list[str] | None,
    on_judgment_start: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    if not judge_config_id or not judge_models:
        return []

    judge_prompt, require_explanation = get_configuration_details(judge_config_id)

    if not judge_prompt:
        return []

    judge_prompt = compose_judge_prompt(judge_prompt, system_prompt, prompt, response)
    failed_judgments = []

    for i, judge_model in enumerate(judge_models, start=1):
        if i > 1:
            time.sleep(openrouter_api.REQUEST_DELAY_S)

        if on_judgment_start:
            on_judgment_start(i, len(judge_models))

        try:
            judge_result = get_judge_result(judge_prompt, judge_model, require_explanation)
        except (OpenRouterRequestError, ModelResponseError) as error:
            failed_model = judge_model

            # if a response was received, show the model that actually generated it
            if isinstance(error, ModelResponseError):
                failed_model = formatting.remove_timestamp_from_model_id(error.model)

            failed_judgments.append(
                {
                    "interaction_id": interaction_id,
                    "judge_model": failed_model,
                    "error": error,
                }
            )
            continue

        # save the judge result into the database
        db.judges.insert_judge_result(
            {
                "interaction_id": interaction_id,
                "judge_config_id": judge_config_id,
                "judge_model": judge_result["judge_model"],
                "label": judge_result["label"],
                "explanation": judge_result["explanation"][:500] if require_explanation else None,
                "time": judge_result["time"],
                "duration": str(judge_result["duration"]),
                "price": judge_result["price"],
            }
        )

    return failed_judgments
