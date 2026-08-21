import json

import pandas as pd
import streamlit as st

from src import database, view_utils, widgets

view_utils.page_config("History")

LABEL_OPTIONS = ["🟢", "🔴", "🟡"]


def save_changes(original_data: pd.DataFrame):
    # delete rows
    for row_idx in changes["deleted_rows"]:
        database.delete_prompt_record(int(original_data.iloc[row_idx]["id"]))

    # adjust record data
    for row_idx, ch in changes["edited_rows"].items():
        preset_id = int(original_data.iloc[row_idx]["id"])

        # label:
        if ch.get("manual_label"):
            database.set_interaction_label(preset_id, ch.get("manual_label"))

        # categories:
        if ch.get("categories"):
            new_value = json.dumps(ch.get("categories"), ensure_ascii=False)
            database.set_interaction_categories(preset_id, new_value)



st.title("History")

# if we have been redirected here, display the passed error message
error_message = st.session_state.pop("error_message", None)
if error_message:
    st.error(error_message)

history_table = view_utils.get_all_history_entries()

if not history_table.empty:
    edited_history_table = st.data_editor(
        history_table,
        key="history_editor",
        height="content",
        hide_index=True,
        num_rows="delete",

        column_order=[
            "id",
            "preset_id",
            "manual_label",
            "judge_label",
            "categories",
            "prompt",
            "system_prompt",
            "response",
            "time",
            "model",
        ],

        disabled=[
            "id",
            "judge_label",
            "prompt",
            "system_prompt",
            "response",
            "time",
            "preset_id",
            "model",
        ],

        column_config={
            "id": st.column_config.TextColumn("ID"),
            "manual_label": st.column_config.SelectboxColumn(
                "Label",
                options=LABEL_OPTIONS,
                required=True,
            ),
            "judge_label": st.column_config.SelectboxColumn(
                "Judge Label",
                options=LABEL_OPTIONS,
                required=True,
            ),
            "categories": st.column_config.MultiselectColumn(
                "categories",
                options=view_utils.get_all_categories(history_table),
                accept_new_options=True,
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
            "preset_id": st.column_config.TextColumn(
                "Preset",
            ),
            "model": st.column_config.TextColumn(
                "Model",
            ),
        },
    )

    # show the save button if there are changes
    changes = st.session_state["history_editor"]

    if len(changes["edited_rows"]) + len(changes["deleted_rows"]) > 0:
        if st.button("Save data", type="primary"):
            save_changes(history_table)
            st.success("Saved!")

    st.space("medium")

    widgets.batch_ids_picker(history_table=history_table)
else:
    st.info("No data yet!")
