import streamlit as st

from llm_workbench.ui import page

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


##### WORKFLOW
st.subheader("Workflow")

for row_start in range(0, len(WORKFLOW_STEPS), 3):
    for column, (page_path, label, icon, description) in zip(
            st.columns(3), WORKFLOW_STEPS[row_start:row_start + 3]
    ):
        with column.container(border=True, height="stretch"):
            st.page_link(page_path, label=label, icon=icon)
            st.caption(description)
