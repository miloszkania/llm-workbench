import streamlit as st
from openrouter import components

from src import formatting, openrouter_api


###### UTILS

def page_config(name: str | None = None) -> None:
    st.set_page_config(
        layout="wide",
        page_title=f"{name} | LLM Workbench" if name else "LLM Workbench"
    )


###### MODELS


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
