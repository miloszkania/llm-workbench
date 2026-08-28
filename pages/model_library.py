import streamlit as st
import pandas as pd

from src import view_utils, widgets, database


view_utils.page_config("Model library")

st.title("Model library")

# Favorite models
st.header("Favorite models")

favorite_models = database.get_favorite_models()
all_model_ids = [i.id for i in view_utils.get_models()]

# also include models that are currently not available
all_model_ids += [model_id for model_id in favorite_models if model_id not in all_model_ids]

selected_favorite_models = st.multiselect(
    "Favorite models",
    options=all_model_ids,
    default=favorite_models,
)

if st.button("Save favorites"):
    database.update_favorite_models(selected_favorite_models)
    favorite_models = selected_favorite_models
    st.success("Saved!")

st.divider()


# All models
st.header("All models")

# Filtering and sorting
models, _ = widgets.model_filter_and_sort_controls(key_prefix="model_library_")
st.space()

table_data = pd.DataFrame(
    [
        {
            "favorite": model.id in favorite_models,
            "id": model.id,
            "description": model.description,
            "context_length": model.context_length,
            "knowledge_cutoff": model.knowledge_cutoff,
            "price_input": float(model.pricing.prompt) * 1_000_000,
            "price_output": float(model.pricing.completion) * 1_000_000,
        }
        for model in models
    ],
    columns=[
        "favorite", "id", "description", "context_length", "knowledge_cutoff", "price_input", "price_output",
    ]
)

# use model id as a stable row index for the dataframe
table_data = table_data.set_index("id", drop=False)

edited_table = st.data_editor(
    table_data,
    height="content",
    hide_index=True,
    disabled=["id", "description", "context_length", "knowledge_cutoff", "price_input", "price_output"],
    column_config={
        "favorite": st.column_config.CheckboxColumn(
            "Favorite", help="Add this model to favorites"
        ),
        "id": st.column_config.TextColumn("ID"),
        "description": st.column_config.TextColumn("Description"),
        "context_length": st.column_config.NumberColumn(
            "Context", help="Maximal context length",
        ),
        "knowledge_cutoff": st.column_config.DatetimeColumn(
            "Knowledge cutoff", format="YYYY-MM-DD",
        ),
        "price_input": st.column_config.NumberColumn(
            "Input", help="Price per 1M input tokens", format="dollar",
        ),
        "price_output": st.column_config.NumberColumn(
            "Output", help="Price per 1M output tokens", format="dollar",
        ),
    }
)

# get favorite state of models currently visible in the table
visible_favorite_dict = edited_table["favorite"].to_dict()

# show favorite models, including those that are hidden by the currently set filter
updated_favorite_models = favorite_models.copy()

for model_id, is_favorite in visible_favorite_dict.items():
    # add model if it wasn't in favorites yet
    if model_id not in updated_favorite_models and is_favorite:
        updated_favorite_models.append(model_id)

    # remove model
    elif model_id in updated_favorite_models and not is_favorite:
        updated_favorite_models.remove(model_id)

# save changes if existent
if updated_favorite_models != favorite_models:
    database.update_favorite_models(updated_favorite_models)
    st.rerun()
