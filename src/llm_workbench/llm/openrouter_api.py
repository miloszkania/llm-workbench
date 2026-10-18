import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Literal

from openrouter import OpenRouter, components, operations

from llm_workbench.config import get_env_config
from llm_workbench.errors import OPENROUTER_ERRORS, ModelResponseError, OpenRouterRequestError

API_TIMEOUT_MS = 30_000  # network timeout for each metadata or model attempt
CHAT_TIMEOUT_MS = 120_000  # network timeout for each chat attempt

RATE_LIMIT_DELAY_S = 4  # default delay when rate-limited and no http retry-after value specified
RETRY_DELAY_S = 3.2  # default delay when not rate-limited
REQUEST_DELAY_S = 3.2  # pause between consecutive requests of a batch to avoid rate limits

TARGET_MAX_COMPLETION_TOKENS = 4_096
JUDGE_MAX_COMPLETION_TOKENS = 1_024

client = OpenRouter(
    api_key=get_env_config().openrouter_api_key,
    retry_config=None,  # disable SDK retries, _safe_run handles them
)


# runs `function` with `**kwargs` as arguments. retries when specified errors occur.
# if the error persists, throws a local error class, simplifying the error validation in other functions
def _safe_run(
    function: Callable[..., Any],
    max_retries: int = 2,
    **kwargs: Any,
) -> Any:
    for attempt in range(max_retries + 1):
        try:
            return function(**kwargs)

        except tuple(OPENROUTER_ERRORS.keys()) as error:
            error_specs = OPENROUTER_ERRORS.get(type(error)) or next(
                specs for error_type, specs in OPENROUTER_ERRORS.items() if isinstance(error, error_type)
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


def get_model_list(sort: str = "most-popular") -> list[components.Model]:
    model_list = _safe_run(client.models.list, sort=sort, timeout_ms=API_TIMEOUT_MS)
    return model_list.result.data


def send_prompt(
    model: str,
    prompt: str,
    system_prompt: str | None,
    conversation_type: Literal["target", "judge"],
) -> tuple[components.ChatResult, datetime, timedelta]:
    # prepare the messages object
    messages = []
    if system_prompt:
        messages.append(
            {
                "role": "system",
                "content": system_prompt,
            }
        )

    messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

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


def get_key_metadata() -> operations.GetCurrentKeyData:
    metadata = _safe_run(client.api_keys.get_current_key_metadata, timeout_ms=API_TIMEOUT_MS)
    return metadata.data


def get_credits() -> operations.GetCreditsData:
    credits_data = _safe_run(client.credits.get_credits, timeout_ms=API_TIMEOUT_MS)
    return credits_data.data


def get_model_object(model_id: str) -> components.ModelResponse:
    author, slug = model_id.split("/", maxsplit=1)
    model_object = _safe_run(client.models.get, author=author, slug=slug, timeout_ms=API_TIMEOUT_MS)
    return model_object


def extract_response_text(response: components.ChatResult) -> str:
    if not response.choices:
        raise ModelResponseError("The model returned no response choices.", response.model)

    choice = response.choices[0]
    message = choice.message
    content = message.content

    if isinstance(content, str) and content.strip():
        return content.strip()

    refusal = message.refusal

    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip()

    if choice.finish_reason == "length":
        raise ModelResponseError(
            "The model reached its completion token limit before returning a final response.", response.model
        )

    raise ModelResponseError("The model returned no textual response.", response.model)


# returns (total tokens, cost). both can be missing in the response, e.g. for some providers
def extract_usage(response: components.ChatResult) -> tuple[int | None, float | None]:
    usage = response.usage

    if usage is None:
        return None, None

    # cost may be None or the SDK's `Unset` sentinel, which can't be stored in the database
    cost = usage.cost if isinstance(usage.cost, (int, float)) else None

    return usage.total_tokens, cost
