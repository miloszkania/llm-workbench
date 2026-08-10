import streamlit as st

from src import view_utils, widgets

st.set_page_config(
    layout="wide",
    page_title="Pipeline: Prompt Details"
)

LABEL_OPTIONS = ["🟢", "🔴", "🟡"]


# get prompt id
if "id" not in st.query_params:
    st.switch_page("pages/history.py")
prompt_id = int(st.query_params["id"])


# initialize change listeners
if "categories_changed" not in st.session_state:
    st.session_state.categories_changed = False
if "label_changed" not in st.session_state:
    st.session_state.label_changed = False


history_table = view_utils.get_all_history_entries(fill_null=True)
current_prompt_data = history_table.loc[history_table["id"] == prompt_id]

# prompt not found
if current_prompt_data.empty:
    st.switch_page("pages/history.py")

current_prompt_data = current_prompt_data.iloc[0]


##### HEADER
st.title("Prompt Details")

if st.button("Back to all prompts"):
    st.switch_page("pages/history.py")

st.subheader(f"ID: {prompt_id}")
st.write(f"Run on `{current_prompt_data["time"]}`")


##### MODEL
widgets.model_picker(current_prompt_data)


##### PROMPT
widgets.prompt_input_display(current_prompt_data, history_table)


##### RESPONSE
st.header("Response")
widgets.single_prompt_response_display(current_prompt_data)


##### DETAILS
widgets.prompt_other_information_display(current_prompt_data)