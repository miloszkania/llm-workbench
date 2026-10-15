import json

import pandas as pd
import streamlit as st

from llm_workbench import database, records
from llm_workbench.ui import page

page.page_config("Presets")


def save_changes(original_df: pd.DataFrame) -> None:
    # Delete rows
    for i in changes["deleted_rows"]:
        database.delete_preset(int(original_df.iloc[i]["id"]))

    # Adjust preset data
    for row_idx, ch in changes["edited_rows"].items():
        for column, new_value in ch.items():
            if column == "categories":
                new_value = json.dumps(ch.get("categories"), ensure_ascii=False)

            preset_id = int(original_df.iloc[row_idx]["id"])
            database.modify_preset(preset_id, column, new_value)

    # Add new rows
    for ch in changes["added_rows"]:
        database.insert_preset({
            "prompt": ch["prompt"],
            "system_prompt": ch.get("system_prompt"),
            "categories": json.dumps(ch.get("categories"), ensure_ascii=False) if ch.get("categories") else None,
        })



st.title("Presets")

preset_table = records.get_all_presets()

if not preset_table.empty:
    edited_preset_table = st.data_editor(
        preset_table,
        key="preset_editor",
        height="content" if len(preset_table) <= 20 else 750,
        hide_index=True,
        num_rows="dynamic",

        column_order=[
            "id",
            "categories",
            "prompt",
            "system_prompt",
        ],

        disabled=[
            "id",
        ],

        column_config={
            "id": st.column_config.TextColumn(
                "ID",
            ),
            "prompt": st.column_config.TextColumn(
                "Prompt",
                width="large",
                required=True,
            ),
            "system_prompt": st.column_config.TextColumn(
                "System Prompt",
                width="large",
            ),
            "categories": st.column_config.MultiselectColumn(
                "Categories",
                options=records.get_all_categories(preset_table),
                accept_new_options=True,
            ),
        },
    )

    # Show the save button if there are changes
    changes = st.session_state["preset_editor"]

    if len(changes["edited_rows"]) + len(changes["deleted_rows"]) + len(changes["added_rows"]) > 0:
        if st.button("Save changes", type="primary"):
            # check if all presets have a non-empty prompt
            prompts = edited_preset_table["prompt"].astype("string")
            missing_prompts = prompts.isna() | prompts.str.strip().eq("")

            if missing_prompts.any():
                st.error("Every preset must have a non-empty prompt!")
            else:
                save_changes(preset_table)
                st.success("Saved!")

    st.divider()

    if st.button("New prompt"):
        st.switch_page("pages/new_prompt.py")

else:
    st.info("No data yet!")
