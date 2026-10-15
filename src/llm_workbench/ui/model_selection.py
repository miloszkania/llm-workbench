from typing import Any

import streamlit as st
from openrouter import components

from llm_workbench import database, formatting, openrouter_api
from llm_workbench.errors import OpenRouterRequestError
from llm_workbench.ui import error_display


@st.cache_data(ttl="1h", show_spinner="Loading available models…")
def get_models(
        sort: str = "most-popular",
        model_filter: str = "All",
) -> list[components.Model]:
    models = openrouter_api.get_model_list(sort)

    # Get the deserved models
    if model_filter == "Free":
        models = [i for i in models if formatting.is_free_model(i.id)]
    elif model_filter == "Paid":
        models = [i for i in models if not formatting.is_free_model(i.id)]

    return models


@st.cache_data(ttl="1h", show_spinner="Loading model information…")
def get_model_object(model_id: str) -> components.ModelResponse:
    return openrouter_api.get_model_object(model_id)


def model_filter_and_sort_controls(
        canvas: Any = st,
        key_prefix: str = "",
        show_library_link: bool = True,
) -> tuple[list[components.Model], str]:
    sorting_options = {
        "most-popular": "Most popular",
        "newest": "Newest",
        "latency-low-to-high": "Lowest latency",
        "pricing-low-to-high": "Lowest price",
        "throughput-high-to-low": "Highest throughput",
        "intelligence-high-to-low": "Highest intelligence",
        "context-high-to-low": "Largest context window",
    }

    if show_library_link:
        canvas.caption("For details of all available models, visit the [Model Library](/model_library).")

    favorites_only = canvas.toggle(
        "Show only favorite models",
        key=f"{key_prefix}favorites_only"
    )

    model_filter = canvas.segmented_control(
        "Model type",
        options=["All", "Free", "Paid"],
        default="All",
        required=True,
        key=f"{key_prefix}model_filter",
    )

    model_sorting = canvas.segmented_control(
        "Sort by",
        options=list(sorting_options),
        format_func=lambda x: sorting_options[x],
        default="most-popular",
        required=True,
        key=f"{key_prefix}model_sorting",
    )

    try:
        selected_models = get_models(
            model_filter=model_filter,
            sort=model_sorting,
        )
    except OpenRouterRequestError as error:
        error_display.display_error(error, canvas)
        return [], model_filter

    if favorites_only:
        favorite_models = database.get_favorite_models()
        selected_models = [i for i in selected_models if i.id in favorite_models]

    return selected_models, model_filter


def model_picker(
        default_model: str | None = None,
        canvas: Any = st,
        key_prefix: str = "",
) -> None:
    models, model_filter = model_filter_and_sort_controls(canvas, key_prefix)
    model_ids = [model.id for model in models]

    # Starting a new prompt, with no previous data as placeholder
    if not default_model:
        selected_model_id = canvas.selectbox(
            "Select a model",
            placeholder="Model",
            options=model_ids,
            index=None,
            key=f"{key_prefix}model",
        )

    # There is placeholder data, and it's present in the up-to-date model list
    elif default_model in model_ids:
        selected_model_id = canvas.selectbox(
            "Select a model",
            placeholder=default_model,
            options=model_ids,
            index=model_ids.index(default_model),
            key=f"{key_prefix}model",
        )

    # There is placeholder data, but it's not present in the up-to-date model list
    else:
        selected_model_id = canvas.selectbox(
            "Select a model",
            placeholder=default_model,
            options=model_ids,
            index=None,
            key=f"{key_prefix}model",
        )

    def set_random_free_model(): st.session_state[f"{key_prefix}model"] = "openrouter/free"

    # Button for "openrouter/free" - random model will be selected
    if model_filter == "Free" and "openrouter/free" in model_ids:
        canvas.button(
            "Random free model",
            type="secondary",
            on_click=set_random_free_model,
            key=f"{key_prefix}random_model_button",
        )

    # Model pricing
    if selected_model_id:
        try:
            model_object = get_model_object(selected_model_id)

            if float(model_object.data.pricing.prompt) >= 0 and float(model_object.data.pricing.completion) >= 0:
                canvas.caption(f"***Price***: starting at "
                     f"**{formatting.format_model_price(model_object.data.pricing.prompt, markdown=True)} "
                               f"per 1M input tokens** · "
                     f"**{formatting.format_model_price(model_object.data.pricing.completion, markdown=True)} "
                               f"per 1M output tokens**")
            else:
                canvas.caption("***Price***: varies by model")

        except OpenRouterRequestError as error:
            error_display.display_error(error, canvas)
