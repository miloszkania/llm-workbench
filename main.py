import streamlit as st

from src.config import get_env_config, EnvironmentConfigError


# Check the presence of required environment variables
try:
    env_config = get_env_config()
except EnvironmentConfigError as e:
    st.error(f"Configuration error: {e}")
    st.stop()


from src import widgets, view_utils

view_utils.page_config()


# Define all subpages
new_prompt = st.Page("pages/new_prompt.py", title="New Prompt")
history = st.Page("pages/history.py", title="History")
presets = st.Page("pages/presets.py", title="Presets")
prompt_details = st.Page("pages/prompt_details.py", title="Prompt Details", visibility="hidden")
batch_details = st.Page("pages/batch_details.py", title="Batch Details", visibility="hidden")
dashboard = st.Page("pages/dashboard.py", title="Dashboard")
dashboard_clean = st.Page("pages/dashboard_clean.py", title="Dashboard (Clean)")
judge_settings = st.Page("pages/judge_settings.py", title="Judge Settings")
new_judge_configuration = st.Page("pages/judge_new_configuration.py", title="New Judge Configuration")


navigation = st.navigation({
    "LLM Workbench": [
        new_prompt,
        judge_settings,
        new_judge_configuration,
        history,
        presets,
        dashboard,
        dashboard_clean,
        prompt_details,
        batch_details,
    ],
})

navigation.run()

widgets.batch_ids_picker(canvas=st.sidebar)

widgets.api_key_details()
