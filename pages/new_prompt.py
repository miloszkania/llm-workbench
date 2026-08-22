import streamlit as st

from src import view_utils, widgets, database

view_utils.page_config("New prompt")


st.title("New Prompt")

##### MODEL
st.header("Model")
widgets.model_picker()


##### PRESET

st.header("Prompt")
all_presets = view_utils.get_all_preset_entries(fill_null=True)

st.page_link("pages/presets.py", label="Edit presets")


# Preset table expander
widgets.preset_table_preview(all_presets)

# After a preset was selected, sets text fields to its data
def fill_preset_fields():
    preset_row = all_presets.loc[all_presets["id"] == st.session_state["preset_id"]]
    if not preset_row.empty:
        preset_row = preset_row.iloc[0]
        st.session_state["system_prompt"] = preset_row["system_prompt"]
        st.session_state["prompt"] = preset_row["prompt"]
        st.session_state["categories"] = preset_row["categories"] if preset_row["categories"] else []

if not all_presets.empty:
    preset = st.selectbox(
        "*Use a preset?*",
        placeholder="Preset ID",
        options=all_presets["id"],
        index=None,
        on_change=fill_preset_fields,
        key="preset_id",
    )

    st.space("small")


##### PROMPT

### Resets the preset ID field
def reset_preset_selection():
    st.session_state["preset_id"] = None

system_prompt = st.text_area(
    "System prompt",
    key="system_prompt",
    on_change=reset_preset_selection,
)
prompt = st.text_area(
    "Prompt",
    key="prompt",
    on_change=reset_preset_selection,
)

categories = st.multiselect(
    "Categories",
    options=view_utils.get_all_categories(),
    accept_new_options=True,
    key="categories",
    on_change=reset_preset_selection,
)

st.space("small")

### Add preset button
widgets.save_preset_button(prompt, system_prompt, categories)

st.divider()


### Judging
st.header("LLM-as-a-Judge Evaluation")

# Fetch the judging configuration
judge_config, judge_models = database.get_default_judge_settings()

judging_enabled = st.toggle(
    "Evaluate responses with LLM judges",
    value=(judge_config and judge_models),
)

if judging_enabled:
    st.write("The following judge configuration and models will be used to independently evaluate every generated "
             "target response.")
    judge_models, judge_config = widgets.judge_model_and_configuration_selector()

else:
    judge_models, judge_config = [], None

st.divider()


### Send button
widgets.send_prompt_button_with_repetitions(judge_config, judge_models)
