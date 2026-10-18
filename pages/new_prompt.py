import streamlit as st

from llm_workbench import db, formatting, records
from llm_workbench.ui import (
    error_display,
    judge_selection,
    model_selection,
    page,
    prompt_controls,
    run_controls,
    system_prompt_controls,
)

page.page_config("New prompt")


st.title("New Prompt")

##### MODEL
st.header("Model")
model_selection.model_picker()
st.divider()


##### SAVED PROMPT

st.header("Prompt")
saved_prompts = records.get_prompts_by_recent_use()

st.page_link("pages/prompts.py", label="Show all prompts")


# After a saved prompt was selected, sets text fields to its data
def fill_saved_prompt_fields():
    prompt_row = saved_prompts.get(st.session_state["saved_prompt_id"])
    if prompt_row:
        st.session_state["system_prompt"] = prompt_row["system_prompt"]
        st.session_state["prompt"] = prompt_row["prompt"]
        st.session_state["categories"] = formatting.parse_categories_from_json(prompt_row["categories"]) or []


if saved_prompts:
    st.selectbox(
        "*Start from a saved prompt?*",
        placeholder="Select a prompt",
        options=list(saved_prompts),
        format_func=lambda prompt_id: prompt_controls.format_prompt_option(saved_prompts[prompt_id]),
        index=None,
        on_change=fill_saved_prompt_fields,
        key="saved_prompt_id",
    )


##### PROMPT


### Resets the saved prompt selection
def reset_saved_prompt_selection():
    st.session_state["saved_prompt_id"] = None


prompt = st.text_area(
    "Prompt",
    key="prompt",
    on_change=reset_saved_prompt_selection,
)

system_prompt = system_prompt_controls.system_prompt_input("system_prompt", on_change=reset_saved_prompt_selection)

categories = st.multiselect(
    "Categories",
    options=records.get_all_categories(),
    accept_new_options=True,
    key="categories",
    on_change=reset_saved_prompt_selection,
)

### Save prompt button
prompt_controls.save_prompt_button(prompt, system_prompt, categories)

st.divider()


### Judging
st.header("LLM-as-a-Judge Evaluation")

# Fetch the judging configuration
judge_config, judge_models = db.settings.get_default_judge_settings()

judging_enabled = st.toggle(
    "Evaluate responses with LLM judges",
    value=bool(judge_config and judge_models),
)

if judging_enabled:
    st.write(
        "The following judge configuration and models will be used to independently evaluate every generated "
        "target response."
    )
    judge_config, judge_models = judge_selection.judge_model_and_configuration_selector(judge_config, judge_models)
else:
    judge_config, judge_models = None, []

st.divider()


### Send button
if (not judging_enabled) or (judging_enabled and judge_models and judge_config):
    run_controls.send_prompt_button_with_repetitions(judge_config, judge_models)
else:
    st.info("Select a valid judge configuration and models or disable LLM judging to continue.")


### Information about failed interactions
interaction_errors = st.session_state.pop("interaction_errors", [])
succeeded_interaction_count = st.session_state.pop("succeeded_interaction_count", 0)
if interaction_errors:
    error_display.display_interaction_errors(
        succeeded_interactions=succeeded_interaction_count,
        interaction_errors=interaction_errors,
    )
