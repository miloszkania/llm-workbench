import json
import re
from datetime import datetime


def parse_categories_from_json(
        text: str | float | None,
) -> list[str] | None:
    if not isinstance(text, str) or not text or text == "[]":
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [text]


def categories_to_json(categories: list[str] | None) -> str | None:
    # no categories are stored as a database null
    return json.dumps(categories, ensure_ascii=False) if categories else None


def normalize_prompt_text(text: str | None) -> str:
    # surrounding whitespace doesn't make a prompt distinct, a missing text is an empty string
    return (text or "").strip()


def remove_timestamp_from_model_id(model_id: str) -> str:
    # removes the snapshot date of the model, e.g. "-20250929" at the end or before a ":variant" suffix
    return re.sub(r"-\d{8}(?=$|:)", "", model_id)


def format_timestamp(value: str) -> str:
    timestamp = datetime.fromisoformat(value)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(value: str) -> str:
    point_position = value.find(".")

    if point_position >= 0: # if there is no dot in value, point_position = -1
        value = value[:value.find(".")]

    hours, minutes, seconds = map(int, value.split(":"))

    # choose the suitable display option
    if hours > 0:
        return value
    elif minutes == 0:
        return f"{seconds} seconds"
    else:
        return f"{minutes} minutes{f' and {seconds} seconds' if seconds != 0 else ''}"


def format_model_price(
        raw_price: str,
        markdown: bool = False,
) -> str:
    price = float(raw_price)

    if markdown:
        return f"\\${(price * 1_000_000):,.2f}" if price >= 0 else "Varies by model"
    else:
        return f"{(price * 1_000_000):,.2f} $" if price >= 0 else "Varies by model"


def is_free_model(model_id: str) -> bool:
    return model_id == "openrouter/free" or model_id.endswith(":free")
