import streamlit as st
import pandas as pd

from src import formatting, view_utils, widgets, database, errors
from src.errors import OpenRouterRequestError

view_utils.page_config("Model library")

st.title("Model library")

# Favorite models
st.header("Favorite models")

favorite_models = database.get_favorite_models()
try:
    all_model_ids = [i.id for i in view_utils.get_models()]
except OpenRouterRequestError as error:
    errors.display_error(error)
    st.stop()

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
model_objects, _ = widgets.model_filter_and_sort_controls(key_prefix="model_library_", show_library_link=False)
st.space()

# Create model library dataframe
model_table = pd.DataFrame(
    [
        {
            "favorite": model_object.id in favorite_models,
            "id": model_object.id,
            "description": model_object.description,
            "context_length": model_object.context_length,
            "knowledge_cutoff": model_object.knowledge_cutoff,
            "input_price": formatting.format_model_price(model_object.pricing.prompt),
            "output_price": formatting.format_model_price(model_object.pricing.completion),
        }
        for model_object in model_objects
    ],
    columns=[
        "favorite", "id", "description", "context_length", "knowledge_cutoff", "input_price", "output_price",
    ]
)

# use model id as a stable row index for the dataframe
model_table = model_table.set_index("id", drop=False)

edited_table = st.data_editor(
    model_table,
    height="content" if len(model_table) <= 20 else 750,
    hide_index=True,
    disabled=["id", "description", "context_length", "knowledge_cutoff", "input_price", "output_price"],
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
        "input_price": st.column_config.TextColumn(
            "Input", help="Price per 1M input tokens", alignment="right",
        ),
        "output_price": st.column_config.TextColumn(
            "Output", help="Price per 1M output tokens", alignment="right",
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
