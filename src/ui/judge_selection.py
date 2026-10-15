import streamlit as st

from src import database, formatting
from src.errors import OpenRouterRequestError
from src.ui import error_display, model_selection


def judge_model_and_configuration_selector(
        default_config: str | None = None,
        default_models: list[str] | None = None,
) -> tuple[str | None, list[str]]:
    if not default_config and not default_models:
        default_config, default_models = database.get_default_judge_settings()

    # Models
    st.subheader("Models")
    st.write("Select up to three models that will evaluate the interactions following your selected configuration.")

    # Not using model_selection.model_picker() here since we need a multiselect instead of a selectbox
    models, _ = model_selection.model_filter_and_sort_controls(key_prefix="judge_")
    model_ids = [model.id for model in models]

    # load the current models and check if they are still available
    previous_selected_models = [m for m in default_models if m in model_ids] if default_models else []

    # to prevent already picked options from getting removed when changing model filters,
    # include them as possible options even if they don't match the filter.
    currently_selected_models = st.session_state.get("selected_judge_models", previous_selected_models)
    model_options = model_ids + [m for m in currently_selected_models if not m in model_ids]

    selected_models_ids = st.multiselect(
        "Select up to three judge models",
        options=model_options,
        default=previous_selected_models,
        max_selections=3,
        filter_mode="contains",
        key="selected_judge_models",
    )

    # Model pricing
    if selected_models_ids:
        st.space()
        st.caption("**Starting prices:**")

        price_table_rows = []
        for model_id in selected_models_ids:
            try:
                model_object = model_selection.get_model_object(model_id)
                price_table_rows.append({
                    "Model": model_id,
                    "Input / 1M tokens": formatting.format_model_price(model_object.data.pricing.prompt),
                    "Output / 1M tokens": formatting.format_model_price(model_object.data.pricing.completion),
                })
            except OpenRouterRequestError as error:
                error_display.display_error(error)
                price_table_rows.append({
                    "Model": model_id,
                    "Input / 1M tokens": "Pricing unavailable",
                    "Output / 1M tokens": "Pricing unavailable",
                })

        st.dataframe(price_table_rows, hide_index=True)


    # Configuration
    st.space()
    st.subheader("Configuration")

    saved_configuration_ids = database.get_saved_configuration_ids()
    previous_selected_configuration = (
        saved_configuration_ids.index(default_config) if default_config in saved_configuration_ids else None
    )

    selected_configuration = st.selectbox(
        "Select a configuration",
        options=saved_configuration_ids,
        index=previous_selected_configuration,
    )

    return selected_configuration, selected_models_ids
