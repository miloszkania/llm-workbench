import streamlit as st

from llm_workbench import db, formatting, records
from llm_workbench.errors import OpenRouterRequestError
from llm_workbench.ui import error_display, page, sidebar

page.page_config()

# page, label, icon and description of every workflow step, in the order they are usually used
WORKFLOW_STEPS = [
    ("pages/judge_settings.py", "1 · Judge Settings", ":material/gavel:", "Configure the LLM-as-a-Judge graders."),
    ("pages/model_library.py", "2 · Model Library", ":material/view_list:", "Browse the target models on OpenRouter."),
    ("pages/new_prompt.py", "3 · New Prompt", ":material/play_arrow:", "Run a prompt against a model several times."),
    ("pages/prompts.py", "4 · Results", ":material/fact_check:", "Open a prompt to review and relabel its responses."),
    ("pages/history.py", "5 · History", ":material/history:", "Browse every response across all prompts."),
    ("pages/analytics.py", "6 · Analytics", ":material/bar_chart:", "Compare success rates across models and categories."),
]


st.title("LLM Workbench")
st.caption("Run jailbreak experiments against LLMs, grade the responses with judges, and compare the results.")


##### STATUS
api_key_column, judge_column, data_column = st.columns(3)

# the loaders are cached, so this shares its requests with the sidebar
with api_key_column.container(border=True, height="stretch"):
    try:
        credits = sidebar.get_credits()
        remaining_credits = credits.total_credits - credits.total_usage
        st.markdown(":green[:material/check: **API key valid**]")
        st.caption(f"${remaining_credits:.2f} credits left")
    except OpenRouterRequestError as error:
        error_display.display_error(error, context="Could not check the API key.")

judge_config_count = len(db.judges.get_all_judge_configurations())
with judge_column.container(border=True, height="stretch"):
    st.markdown(f"**{formatting.pluralize(judge_config_count, 'judge configuration')}**")
    st.page_link("pages/judge_settings.py", label="Manage judges")

prompt_overview = records.get_prompt_overview()
response_count = int(prompt_overview["interaction_count"].sum()) if not prompt_overview.empty else 0
with data_column.container(border=True, height="stretch"):
    st.markdown(f"**{formatting.pluralize(len(prompt_overview), 'prompt')}**")
    st.caption(formatting.pluralize(response_count, "response"))


##### WORKFLOW
st.subheader("Workflow")

for row_start in range(0, len(WORKFLOW_STEPS), 3):
    for column, (page_path, label, icon, description) in zip(
            st.columns(3), WORKFLOW_STEPS[row_start:row_start + 3]
    ):
        with column.container(border=True, height="stretch"):
            st.page_link(page_path, label=label, icon=icon)
            st.caption(description)
