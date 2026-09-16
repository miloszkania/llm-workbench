from datetime import datetime
import time

from openrouter import OpenRouter

from src.config import get_env_config
from src.errors import OpenRouterRequestError, OPENROUTER_ERRORS

API_TIMEOUT_MS = 30_000 # network timeout for each metadata or model attempt
CHAT_TIMEOUT_MS = 120_000 # network timeout for each chat attempt

RATE_LIMIT_DELAY_S = 4 # default delay when rate-limited and no http retry-after value specified
RETRY_DELAY_S = 3.2 # default delay when not rate-limited

TARGET_MAX_COMPLETION_TOKENS = 4_096
JUDGE_MAX_COMPLETION_TOKENS = 1_024

client = OpenRouter(
    api_key=get_env_config().openrouter_api_key,
    retry_config=None, # disable SDK retries, _safe_run handles them
)

# runs `function` with `**kwargs` as arguments. retries when specified errors occur.
# if the error persists, throws a local error class, simplifying the error validation in other functions
def _safe_run(function, max_retries=2, **kwargs):
    for attempt in range(max_retries + 1):
        try:
            return function(**kwargs)

        except tuple(OPENROUTER_ERRORS.keys()) as error:
            error_specs = (
                OPENROUTER_ERRORS.get(type(error))
                or next(
                    specs for error_type, specs in OPENROUTER_ERRORS.items()
                    if isinstance(error, error_type)
                )
            )

            # stop trying (raise) if we encountered a non-retry error or if this is the last attempt
            if not error_specs["retry"] or attempt == max_retries:
                raise OpenRouterRequestError(
                    message=error_specs["message"],
                    kind=error_specs["kind"],
                    original_error=error,
                ) from error

            # specify sleep times if we encountered a rate limit error
            if error_specs["kind"] == "rate_limit":
                # try to fetch the retry-after http header
                try:
                    retry_after = error.headers.get("retry-after")
                    delay = float(retry_after)

                # if non-existent or wrongly formatted, fix the delay
                except (TypeError, ValueError):
                    delay = RATE_LIMIT_DELAY_S
            else:
                delay = RETRY_DELAY_S

            time.sleep(delay)


def get_model_list(sort="most-popular"):
    model_list = _safe_run(client.models.list, sort=sort, timeout_ms=API_TIMEOUT_MS)
    return model_list.result.data


def send_prompt(model, prompt, system_prompt, conversation_type):
    # prepare the messages object
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

    # set the right completion tokens limit
    if conversation_type == "target":
        max_completion_tokens = TARGET_MAX_COMPLETION_TOKENS
    elif conversation_type == "judge":
        max_completion_tokens = JUDGE_MAX_COMPLETION_TOKENS
    else:
        max_completion_tokens = None

    # measure running time
    timestamp_start = datetime.now()

    response = _safe_run(
        client.chat.send,
        model=model,
        messages=messages,
        timeout_ms=CHAT_TIMEOUT_MS,
        max_completion_tokens=max_completion_tokens,
    )

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
