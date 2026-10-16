import pandas as pd
import streamlit as st

from llm_workbench import db, formatting, records
from llm_workbench.ui import editor_changes, page

page.page_config("History")

label_options = ["success", "refusal", "unclear"]

def save_changes(original_data: pd.DataFrame) -> None:
    for interaction_id in editor_changes.deleted_ids(changes, original_data):
        db.interactions.delete_interaction(interaction_id)

    # only the manual label is editable, categories belong to the prompt
    for interaction_id, edited_columns in editor_changes.edited_rows_by_id(changes, original_data).items():
        if "manual_label" in edited_columns:
            db.interactions.set_interaction_label(interaction_id, edited_columns["manual_label"])


st.title("History")

# if we have been redirected here, display the passed error message
error_message = st.session_state.pop("error_message", None)
if error_message:
    st.error(error_message)

history_table = records.get_all_interactions()

if not history_table.empty:
    # link every interaction to the results page of its prompt
    history_table["prompt_link"] = history_table["prompt_id"].map(formatting.format_results_page_url)

    edited_history_table = st.data_editor(
        history_table,
        key="history_editor",
        height="content" if len(history_table) <= 20 else 750,
        hide_index=True,
        num_rows="delete",

        column_order=[
            "id",
            "prompt_link",
            "manual_label",
            "categories",
            "prompt",
            "response",
            "time",
            "model",
            "system_prompt",
        ],

        disabled=[
            "id",
            "prompt_link",
            "categories",
            "prompt",
            "system_prompt",
            "response",
            "time",
            "model",
        ],

        column_config={
            "id": st.column_config.TextColumn("ID"),
            "prompt_link": st.column_config.LinkColumn(
                "Prompt ID",
                display_text=formatting.RESULTS_PAGE_URL_PROMPT_ID_PATTERN,
                help="Open the results of all interactions with this prompt",
            ),
            "manual_label": st.column_config.SelectboxColumn(
                "Label",
                options=label_options,
                format_func=lambda x: x.capitalize(),
            ),
            "categories": st.column_config.MultiselectColumn(
                "Categories",
                help="Categories belong to the prompt and can be edited on the Prompts page",
            ),
            "time": st.column_config.DatetimeColumn(
                "Timestamp",
                format="DD.MM.YYYY HH:mm",
            ),
            "prompt": st.column_config.TextColumn(
                "Prompt",
                width="large",
            ),
            "system_prompt": st.column_config.TextColumn(
                "System Prompt",
                width="large",
            ),
            "response": st.column_config.TextColumn(
                "Response",
                width="large",
            ),
            "model": st.column_config.TextColumn(
                "Model",
            ),
        },
    )

    # show the save button if there are changes
    changes = st.session_state["history_editor"]

    if editor_changes.has_changes(changes):
        if st.button("Save data", type="primary"):
            save_changes(history_table)
            st.success("Saved!")
else:
    st.info("No data yet!")
