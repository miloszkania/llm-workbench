import streamlit as st

from llm_workbench.config import get_env_config, EnvironmentConfigError


# Check the presence of required environment variables
try:
    env_config = get_env_config()
except EnvironmentConfigError as error:
    st.error(f"Configuration error: {error}")
    st.stop()


from llm_workbench.ui import page, sidebar

page.page_config()


# Define all subpages
home = st.Page("pages/home.py", title="Home", default=True)
new_prompt = st.Page("pages/new_prompt.py", title="New Prompt")
analytics_page = st.Page("pages/analytics.py", title="Analytics")
prompts = st.Page("pages/prompts.py", title="Prompts")
history = st.Page("pages/history.py", title="History")
experiment_results = st.Page("pages/experiment_results.py", title="Experiment Results", visibility="hidden")
judge_settings = st.Page("pages/judge_settings.py", title="Judge Settings")
new_judge_configuration = st.Page("pages/judge_new_configuration.py", title="New Judge Configuration", visibility="hidden")
model_library = st.Page("pages/model_library.py", title="Model Library")


navigation = st.navigation({
    "LLM Workbench": [
        home,
        new_prompt,
        analytics_page,
        judge_settings,
        model_library,
        new_judge_configuration,
        prompts,
        history,
        experiment_results,
    ],
})

# render the sidebar before the page, so a page calling st.stop() doesn't hide it
sidebar.prompt_picker()
sidebar.api_key_details()

navigation.run()
