import pandas as pd
import streamlit as st

from llm_workbench import db
from llm_workbench.ui import judge_selection, page

page.page_config("Judge settings")

st.title("Judge Settings")

# Show information about a successfully created config (when redirected here from the add-page)
created_config_name = st.session_state.pop("created_config", None)
if created_config_name:
    st.success(f"A new configuration `{created_config_name}` has been successfully created!")

# Load existing configurations
all_configs = pd.DataFrame(db.judges.get_all_judge_configurations())


if not all_configs.empty:
    ### Default settings
    st.header("Default settings")

    # get current default settings
    judge_config, judge_models = db.settings.get_default_judge_settings()

    judging_enabled = st.toggle(
        "Evaluate responses with LLM judges",
        value=bool(judge_config and judge_models),
    )

    if judging_enabled:
        st.write("The following judge configuration and models will be used by default when [sending a new prompt](/).")
        st.space()

        selected_config, selected_models = judge_selection.judge_model_and_configuration_selector(
            judge_config, judge_models
        )
        st.space()
    else:
        selected_models, selected_config = [], None

    if st.button("Save defaults", type="primary"):
        if judging_enabled and (not selected_config or not selected_models):
            st.error("Select a judge configuration and at least one judge model!")
        else:
            db.settings.modify_default_judge_settings(selected_config, selected_models)
            st.success("Saved!")

    st.divider()

    ### All configurations
    st.header("Saved configurations")

    if st.button("Add new configuration"):
        st.switch_page("pages/judge_new_configuration.py")

    st.space()

    for config in all_configs.to_dict("records"):
        with st.container(border=True):
            st.markdown(f"**{config['id']}**")

            badges = []
            if config["id"] == judge_config:
                badges.append(":green-badge[Default]")
            if config["require_explanation"] == 1:
                badges.append(":blue-badge[Explanation required]")
            else:
                badges.append(":gray-badge[Label only]")
            st.markdown(" ".join(badges))

            with st.expander("Introductory prompt"):
                st.code(config["judge_prompt"], language=None, wrap_lines=True)

else:
    st.info("No configurations yet!")
    if st.button("Add new configuration", type="primary"):
        st.switch_page("pages/judge_new_configuration.py")
