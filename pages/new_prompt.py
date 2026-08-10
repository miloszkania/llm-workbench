import streamlit as st

from src import view_utils, widgets

st.set_page_config(
    layout="wide",
    page_title="Pipeline: New Prompt"
)


st.title("New Prompt")

##### MODEL
widgets.model_picker()


##### PRESET

st.subheader("Prompt")
all_presets = view_utils.get_all_preset_entries(fill_null=True)

st.page_link("pages/presets.py", label="Edit presets")


# Preset table expander
widgets.preset_table_preview(all_presets)

# After a preset was selected, sets text fields to its data
def fill_preset_fields():
    preset_row = all_presets.loc[all_presets["id"] == st.session_state["preset"]]
    if not preset_row.empty:
        preset_row = preset_row.iloc[0]
        st.session_state["system_prompt"] = preset_row["system_prompt"]
        st.session_state["prompt"] = preset_row["prompt"]
        st.session_state["categories"] = preset_row["categories"]

if not all_presets.empty:
    preset = st.selectbox(
        "*Use a preset?*",
        placeholder="Preset ID",
        options=all_presets["id"],
        index=None,
        on_change=fill_preset_fields,
        key="preset",
    )

    st.space("small")


##### PROMPT

### Resets the preset ID field
def reset_preset_selection():
    st.session_state["preset"] = None

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


##### BUTTONS

### Add preset button
widgets.save_preset_button()


### Send button
widgets.send_prompt_button_with_repetitions()