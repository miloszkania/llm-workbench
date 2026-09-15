from datetime import datetime
import time

import openrouter.errors
from openrouter import OpenRouter

from src.config import get_env_config
from src.errors import OpenRouterRequestError, OPENROUTER_ERRORS

API_TIMEOUT_MS = 30_000 # wait at most 30 s for a metadata or model response (in each attempt)
CHAT_TIMEOUT_MS = 120_000 # wait at most 120 s for a chat response (in each attempt)

client = OpenRouter(
    api_key=get_env_config().openrouter_api_key,
    retry_config=None, # disable SDK retries, _safe_run handles them
)

# runs `function` with `**kwargs` as arguments. retries when specified errors occur.
# if the error persists, throws a local error class, simplifying the error validation in other functions
def _safe_run(function, max_retries=2, **kwargs):
    # see if we will be retrying or directly throwing
    try:
        return function(**kwargs)

    except tuple(OPENROUTER_ERRORS.keys()) as e:
        error_specs = OPENROUTER_ERRORS.get(type(e), OPENROUTER_ERRORS[openrouter.errors.OpenRouterError])

        if error_specs["retry"]:
            # try to send the request `max_retries` more times
            for i in range(max_retries):
                time.sleep(3.2)

                try:
                    return function(**kwargs)
                except tuple(OPENROUTER_ERRORS.keys()) as inner_e:
                    inner_error_specs = OPENROUTER_ERRORS.get(
                        type(inner_e), OPENROUTER_ERRORS[openrouter.errors.OpenRouterError]
                    )

                    # if we got a non-retryable error, stop right away
                    if not inner_error_specs["retry"]:
                        raise OpenRouterRequestError(
                            inner_error_specs["message"],
                            inner_error_specs["kind"],
                            original_error=inner_e
                        ) from inner_e

                    continue

        # all retries used but still no success
        raise OpenRouterRequestError(error_specs["message"], error_specs["kind"], original_error=e) from e


def get_model_list(sort="most-popular"):
    model_list = _safe_run(client.models.list, sort=sort, timeout_ms=API_TIMEOUT_MS)
    return model_list.result.data


def send_prompt(model, prompt, system_prompt):
    # Measure running time
    timestamp_start = datetime.now()

    messages = []
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt,
        })

    messages.append({
        "role": "user",
        "content": prompt,
    })

    response = _safe_run(client.chat.send, model=model, messages=messages, timeout_ms=CHAT_TIMEOUT_MS)
    timestamp_end = datetime.now()

    return response, timestamp_start, timestamp_end - timestamp_start


def get_key_metadata():
    metadata = _safe_run(client.api_keys.get_current_key_metadata, timeout_ms=API_TIMEOUT_MS)
    return metadata.data


def get_credits():
    credits_data = _safe_run(client.credits.get_credits, timeout_ms=API_TIMEOUT_MS)
    return credits_data.data


def get_model_object(model_id):
    author, slug = model_id.split("/", maxsplit=1)
    model_object = _safe_run(client.models.get, author=author, slug=slug, timeout_ms=API_TIMEOUT_MS)
    return model_object


def extract_response_text(response):
    if not response.choices:
        raise ValueError("The model returned no response choices.")

    message = response.choices[0].message
    content = message.content

    if isinstance(content, str) and content.strip():
        return content.strip()

    refusal = message.refusal

    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip()

    raise ValueError("The model returned no textual response.")
