import pandas as pd
import streamlit as st

from src import view_utils, database

view_utils.page_config("Judge settings")

st.title("Judge Settings")

# Show information about a successfully created config (when redirected here from the add-page)
created_config_name = st.session_state.pop("created_config", None)
if created_config_name:
    st.success(f"A new configuration `{created_config_name}` has been successfully created!")

# Load existing configurations
all_configs = pd.DataFrame(database.get_all_judge_configurations())


if not all_configs.empty:
    ### Default settings
    default_config, default_models = database.get_default_judge_settings()

    st.header("Default settings")
    st.write("The following judge configuration and models will be used by default when [sending a new prompt](/).")
    st.space()

    # Models
    st.subheader("Models")
    st.write("Select up to three models that will evaluate the interactions following your selected configuration.")

    # Not using widgets.model_picker() here since we need a multiselect instead of a selectbox
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

        # load the current models and check if they are still available
        previous_selected_models = [m for m in default_models if m in model_ids]

        selected_models = st.multiselect(
            "Select up to 3 judge models",
            options=model_ids,
            default=previous_selected_models,
            max_selections=3,
            filter_mode="contains",
            key="selected_judge_models", # to prevent resetting after changing the filters
        )

    # Configuration
    st.space()
    st.subheader("Configuration")

    with st.spinner("Loading judge configurations…"):
        saved_configuration_names = database.get_saved_configuration_names()
        previous_selected_configuration = (
            saved_configuration_names.index(default_config) if default_config in saved_configuration_names else None
        )

        selected_configuration = st.selectbox(
            "Select a configuration",
            options=saved_configuration_names,
            index=previous_selected_configuration,
        )

    st.space()
    if st.button("Save defaults", type="primary"):
        if not selected_models:
            st.error("You must choose at least one judge model!")
        elif not selected_configuration:
            st.error("You must choose a configuration!")
        else:
            database.modify_default_judge_settings(selected_configuration, selected_models)
            st.success("Saved!")

    st.divider()


    ### Configurations
    st.header("Saved configurations")

    if st.button("Add new configuration"):
        st.switch_page("pages/judge_new_configuration.py")

    st.space()

    all_configs["require_explanation"] = all_configs["require_explanation"].apply(lambda x: x == 1)

    st.dataframe(
        all_configs,
        hide_index=True,
        row_height=100,
        height="content",
        column_order=("name", "judge_prompt", "require_explanation"),
        column_config={
            "name": st.column_config.TextColumn("Name"),
            "judge_prompt": st.column_config.TextColumn("Introductory prompt"),
            "require_explanation": st.column_config.CheckboxColumn("Explanation required?"),
        },
    )

else:
    st.info("No configurations yet!")
    if st.button("Add new configuration", type="primary"):
        st.switch_page("pages/judge_new_configuration.py")
