from datetime import datetime
from openrouter import OpenRouter

from src.config import get_env_config

client = OpenRouter(api_key=get_env_config().openrouter_api_key)


def get_model_list(sort="most-popular"):
    model_list = client.models.list(sort=sort).result.data
    return model_list


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

    response = client.chat.send(
        model=model,
        messages=messages,
    )
    timestamp_end = datetime.now()

    return response, timestamp_start, timestamp_end - timestamp_start


def get_key_metadata():
    return client.api_keys.get_current_key_metadata().data


def get_credits():
    return client.credits.get_credits().data
