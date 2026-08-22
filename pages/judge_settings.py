import pandas as pd
import streamlit as st

from src import view_utils, database, widgets

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
    st.header("Default settings")

    judging_enabled = st.toggle(
        "Evaluate responses with LLM judges",
        value=True,
    )

    if judging_enabled:
        st.write("The following judge configuration and models will be used by default when [sending a new prompt](/).")
        st.space()

        selected_models, selected_configuration = widgets.judge_model_and_configuration_selector()
        st.space()
    else:
        selected_models, selected_configuration = [], None

    if st.button("Save defaults", type="primary"):
        database.modify_default_judge_settings(selected_configuration, selected_models)
        st.success("Saved!")

    st.divider()


    ### All configurations
    st.header("Saved configurations")

    if st.button("Add new configuration"):
        st.switch_page("pages/judge_new_configuration.py")

    st.space()

    all_configs["require_explanation"] = all_configs["require_explanation"].apply(lambda x: x == 1)

    st.dataframe(
        all_configs,
        row_height=100,
        height="content",
        column_order=("id", "judge_prompt", "require_explanation"),
        column_config={
            "id": st.column_config.TextColumn("ID"),
            "judge_prompt": st.column_config.TextColumn("Introductory prompt"),
            "require_explanation": st.column_config.CheckboxColumn("Explanation required?"),
        },
    )

else:
    st.info("No configurations yet!")
    if st.button("Add new configuration", type="primary"):
        st.switch_page("pages/judge_new_configuration.py")
