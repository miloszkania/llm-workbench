from datetime import datetime
from os import getenv

from dotenv import load_dotenv
from openrouter import OpenRouter


load_dotenv()
client = OpenRouter(api_key=getenv("OPENROUTER_API_KEY"))


def get_model_list():
    model_list = client.models.list().data
    return sorted(model_list, key=lambda x: x.id)


def send_prompt(model, prompt, system_prompt):
    # Measure running time
    timestamp_start = datetime.now()
    response = client.chat.send(
        model = model,
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    timestamp_end = datetime.now()

    return response, timestamp_start, timestamp_end - timestamp_start