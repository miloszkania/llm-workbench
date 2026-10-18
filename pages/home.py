from typing import Any

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

def status_tile(column: Any, icon: str) -> Any:
    # a bordered tile with a large icon on the left, returns the container for its text
    tile = column.container(border=True, height="stretch", horizontal=True, vertical_alignment="center", gap="medium")
    tile.markdown(f"<span style='font-size: 3rem; line-height: 1'>{icon}</span>", unsafe_allow_html=True, width="content")
    return tile.container()


# the loaders are cached, so this shares its requests with the sidebar
try:
    credits = sidebar.get_credits()
except OpenRouterRequestError as error:
    with status_tile(api_key_column, ":red[:material/key:]"):
        error_display.display_error(error, context="Could not check the API key.")
else:
    with status_tile(api_key_column, ":green[:material/key:]"):
        st.markdown(":green[**API key valid**]")
        st.caption(f"${credits.total_credits - credits.total_usage:.2f} credits left")

judge_config_count = len(db.judges.get_all_judge_configurations())
with status_tile(judge_column, ":material/gavel:"):
    st.markdown(f"**{formatting.pluralize(judge_config_count, 'judge configuration')}**")
    st.page_link("pages/judge_settings.py", label="Manage judges")

prompt_overview = records.get_prompt_overview()
response_count = int(prompt_overview["interaction_count"].sum()) if not prompt_overview.empty else 0
with status_tile(data_column, ":material/chat:"):
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


##### RECENT RUNS
st.subheader("Recent runs")

recent_runs = records.get_recent_runs()

if not recent_runs:
    st.page_link("pages/new_prompt.py", label="Run your first prompt", icon=":material/play_arrow:")

for run in recent_runs:
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        st.page_link(
            "pages/experiment_results.py",
            label=formatting.format_prompt_label(run["prompt_id"], run["prompt_title"]),
            query_params={"prompt": run["prompt_id"], "run": run["run_id"]},
        )
        st.caption(" · ".join([
            ", ".join(run["models"]),
            formatting.pluralize(run["interaction_count"], "response"),
            formatting.pluralize(run["success_count"], "success", "successes"),
            formatting.format_timestamp(run["started_at"]),
        ]))
