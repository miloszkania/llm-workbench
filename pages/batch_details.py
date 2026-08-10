import streamlit as st

from src import view_utils, widgets

st.set_page_config(
    layout="wide",
    page_title="Pipeline: Batch Details"
)

LABEL_OPTIONS = ["🟢", "🔴", "🟡"]



# get prompt ids
if "ids" not in st.query_params:
    st.switch_page("pages/history.py")


# get the list of record ids and parse it
prompt_ids = st.query_params["ids"]
prompt_ids = prompt_ids.split(",")
batch_size = len(prompt_ids)


# redirect directly to the single prompt details page as there is only one prompt in the batch
if batch_size == 1:
    st.switch_page("pages/prompt_details.py", query_params={"id": prompt_ids[0]})


# initialize change listeners
if "categories_changed" not in st.session_state:
    st.session_state.categories_changed = False
if "label_changed" not in st.session_state:
    st.session_state.label_changed = False


prompt_ids = [int(i) for i in prompt_ids]

history_table = view_utils.get_all_history_entries(fill_null=True)
batch_data = history_table.loc[history_table["id"].isin(prompt_ids)]


# batch not found
if batch_data.empty:
    st.switch_page("pages/history.py")


first_batch_prompt = batch_data.iloc[0]
last_batch_prompt = batch_data.iloc[len(batch_data) - 1]


# check if all prompts have the same content
equal_fields = ["system_prompt", "prompt"]

if batch_data[equal_fields].nunique().max() > 1:
    st.switch_page("pages/history.py")




##### HEADER
st.title("Batch Details")

if st.button("Back to all prompts"):
    st.switch_page("pages/history.py")

st.subheader(f"IDs: {", ".join(map(str, prompt_ids))}")

st.write(f"Run between `{first_batch_prompt["time"]}` and `{last_batch_prompt["time"]}`")


##### MODEL
widgets.model_picker(first_batch_prompt)


##### PROMPT
widgets.prompt_input_display(first_batch_prompt, history_table, prompt_ids)


##### RESPONSE
st.header("Responses")

for prompt_id in prompt_ids:
    current_prompt = batch_data.loc[batch_data["id"] == prompt_id].iloc[0]
    widgets.single_prompt_response_display(current_prompt)


##### DETAILS
widgets.prompt_other_information_display(batch_data[["duration", "token_usage"]].sum())