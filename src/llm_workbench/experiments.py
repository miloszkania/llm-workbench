import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from llm_workbench import db, formatting
from llm_workbench.errors import ModelResponseError, OpenRouterRequestError
from llm_workbench.llm import judge, openrouter_api


@dataclass
class RunResult:
    prompt_id: int
    run_id: str
    interaction_ids: list[int] = field(default_factory=list)
    interaction_errors: list[OpenRouterRequestError | ModelResponseError] = field(default_factory=list)
    failed_judgments: list[dict[str, Any]] = field(default_factory=list)


def generate_and_evaluate_interactions(
    model: str,
    prompt_id: int,
    judge_config: str | None,
    judge_models: list[str] | None,
    repetition_count: int = 1,
    on_interaction_start: Callable[[int, int], None] | None = None,
    on_judgment_start: Callable[[int, int], None] | None = None,
) -> RunResult:
    prompt_object = db.prompts.get_prompt_by_id(prompt_id)

    if prompt_object is None:
        raise ValueError(f"No prompt with ID={prompt_id} exists.")

    prompt = prompt_object["prompt"]
    system_prompt = prompt_object["system_prompt"]

    # all interactions of this call share one run id
    result = RunResult(prompt_id=prompt_id, run_id=uuid.uuid4().hex)

    # send the prompt `repetition_count` times
    for i in range(1, repetition_count + 1):
        # pause between requests (if not first prompt of the batch)
        if i > 1:
            time.sleep(openrouter_api.REQUEST_DELAY_S)

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
            result.interaction_errors.append(error)
            continue

        # clear the model id (remove the timestamp-snapshot)
        used_model = formatting.remove_timestamp_from_model_id(response.model)
        token_usage, price = openrouter_api.extract_usage(response)

        # add the interaction to database
        interaction_id = db.interactions.insert_interaction(
            {
                "prompt_id": prompt_id,
                "run_id": result.run_id,
                "time": str(start_timestamp),
                "model": used_model,
                "response": response_content,
                "duration": str(duration),
                "token_usage": token_usage,
                "price": price,
            }
        )

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
        result.failed_judgments.extend(current_failed_judgments)

        # save the id of the resulting interaction
        result.interaction_ids.append(interaction_id)

    return result
