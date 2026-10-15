import json
import time
from typing import Any, Callable

from llm_workbench import database, formatting, judge, openrouter_api
from llm_workbench.errors import OpenRouterRequestError, ModelResponseError


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
