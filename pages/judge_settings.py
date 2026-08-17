import pandas as pd
import streamlit as st

from src import view_utils, database

view_utils.page_config("Judge settings")

st.title("Judge Settings")

### Default settings
st.header("Default settings")
st.write("The following judge configuration and models will be used by default when [sending a new prompt](/).")
st.space()

# Models
st.subheader("Models")
st.write("Select up to three models that will evaluate the interactions following your selected configuration.")

sorting_options = {
    "most-popular": "Most popular",
    "newest": "Newest",
    "latency-low-to-high": "Lowest latency",
    "pricing-low-to-high": "Lowest price",
    "throughput-high-to-low": "Highest throughput",
    "intelligence-high-to-low": "Highest intelligence",
    "context-high-to-low": "Largest context window",
}

model_filter = st.segmented_control(
    "Model type",
    options=["All", "Free"],
    default="All",
    required=True,
)

model_sorting = st.segmented_control(
    "Sort by",
    options=list(sorting_options),
    format_func=lambda x: sorting_options[x],
    default="most-popular",
    required=True,
)

with st.spinner("Loading available models…"):
    model_ids = view_utils.get_model_ids(only_free_models=model_filter == "Free", sort=model_sorting)

    selected_models = st.multiselect(
        "Select up to 3 judge models",
        options=model_ids,
        max_selections=3,
        filter_mode="contains",
    )

# configuration
st.space()
st.subheader("Configuration")

with st.spinner("Loading judge configurations…"):
    saved_configuration_names = database.get_saved_configuration_names()

    selected_configuration = st.selectbox(
        "Select a configuration",
        options=saved_configuration_names,
    )

st.space()
if st.button("Save defaults", type="primary"):
    pass

st.divider()


### Configurations
st.header("Saved configurations")

if st.button("Add new configuration"):
    st.switch_page("pages/judge_new_configuration.py")

st.space()


all_configs = pd.DataFrame(database.get_all_judge_configurations())
all_configs["require_explanation"] = all_configs["require_explanation"].apply(lambda x: x == 1)

st.dataframe(
    all_configs,
    hide_index=True,
    row_height=150,
    column_order=("name", "judge_prompt", "require_explanation"),
    column_config={
        "name": st.column_config.TextColumn("Name"),
        "judge_prompt": st.column_config.TextColumn("Introductory prompt"),
        "require_explanation": st.column_config.CheckboxColumn("Explanation required?"),
    },
)
