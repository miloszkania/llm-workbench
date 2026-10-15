import streamlit as st

from src.config import get_env_config, EnvironmentConfigError


# Check the presence of required environment variables
try:
    env_config = get_env_config()
except EnvironmentConfigError as error:
    st.error(f"Configuration error: {error}")
    st.stop()


from src.ui import page, sidebar

page.page_config()


# Define all subpages
new_prompt = st.Page("pages/new_prompt.py", title="New Prompt")
analytics_page = st.Page("pages/analytics.py", title="Analytics")
history = st.Page("pages/history.py", title="History")
presets = st.Page("pages/presets.py", title="Presets")
experiment_results = st.Page("pages/experiment_results.py", title="Experiment Results", visibility="hidden")
judge_settings = st.Page("pages/judge_settings.py", title="Judge Settings")
new_judge_configuration = st.Page("pages/judge_new_configuration.py", title="New Judge Configuration", visibility="hidden")
model_library = st.Page("pages/model_library.py", title="Model Library")


navigation = st.navigation({
    "LLM Workbench": [
        new_prompt,
        analytics_page,
        judge_settings,
        model_library,
        new_judge_configuration,
        history,
        presets,
        experiment_results,
    ],
})

navigation.run()

sidebar.batch_ids_picker(canvas=st.sidebar)

sidebar.api_key_details()
