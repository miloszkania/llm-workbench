import pandas as pd
import streamlit as st

from llm_workbench import db, formatting, records
from llm_workbench.ui import editor_changes, page

page.page_config("Prompts")


def save_changes(original_data: pd.DataFrame) -> None:
    for prompt_id in editor_changes.deleted_ids(changes, original_data):
        db.prompts.delete_prompt(prompt_id)

    # the prompt texts are read-only, otherwise they wouldn't match their responses anymore
    for prompt_id, edited_columns in editor_changes.edited_rows_by_id(changes, original_data).items():
        if "title" in edited_columns:
            db.prompts.set_prompt_title(prompt_id, (edited_columns["title"] or "").strip() or None)

        if "categories" in edited_columns:
            db.prompts.set_prompt_categories(prompt_id, formatting.categories_to_json(edited_columns["categories"]))


st.title("Prompts")

# if we have been redirected here, display the passed error message
error_message = st.session_state.pop("error_message", None)
if error_message:
    st.error(error_message)

all_prompts = records.get_prompt_overview()

if all_prompts.empty:
    st.info("No prompts yet! Prompts are saved automatically when you run them.")
else:
    search = st.text_input(
        "Search",
        placeholder="Search titles, prompts and system prompts…",
        label_visibility="collapsed",
    )
    prompt_table = records.search_prompts(all_prompts, search)

    if prompt_table.empty:
        st.info("No prompts match the search.")
    else:
        st.caption(
            "This page displays every saved prompt with its run and label counts. "
            "Only titles and categories can be edited. "
            "Deleting a prompt also deletes all of its responses and their judge results."
        )

        # link every prompt to its results page
        prompt_table["results_link"] = prompt_table["id"].map(formatting.format_results_page_url)

        st.data_editor(
            prompt_table,
            # unsaved edits refer to row positions, and a new search shows different rows,
            # so each search gets its own editor (pending edits are dropped instead of hitting the wrong prompt)
            key=f"prompt_editor_{search}",
            height="content" if len(prompt_table) <= 20 else 750,
            hide_index=True,
            num_rows="delete",
            column_order=[
                "results_link",
                "title",
                "categories",
                "prompt",
                "run_count",
                "interaction_count",
                "success_count",
                "refusal_count",
                "unclear_count",
                "last_run_at",
                "system_prompt",
            ],
            disabled=[
                "results_link",
                "prompt",
                "system_prompt",
                "run_count",
                "interaction_count",
                "success_count",
                "refusal_count",
                "unclear_count",
                "last_run_at",
            ],
            column_config={
                "results_link": st.column_config.LinkColumn(
                    "ID",
                    display_text=formatting.RESULTS_PAGE_URL_PROMPT_ID_PATTERN,
                    help="Open the results of all responses to this prompt",
                ),
                "title": st.column_config.TextColumn("Title"),
                "categories": st.column_config.MultiselectColumn(
                    "Categories",
                    options=records.get_all_categories(all_prompts),
                    accept_new_options=True,
                ),
                "prompt": st.column_config.TextColumn("Prompt", width="large"),
                "run_count": st.column_config.NumberColumn("Runs"),
                "interaction_count": st.column_config.NumberColumn("Responses"),
                "success_count": st.column_config.NumberColumn("Successes", help="Manually labeled as success"),
                "refusal_count": st.column_config.NumberColumn("Refusals", help="Manually labeled as refusal"),
                "unclear_count": st.column_config.NumberColumn("Unclear", help="Manually labeled as unclear"),
                "last_run_at": st.column_config.DatetimeColumn("Last run", format="DD.MM.YYYY HH:mm"),
                "system_prompt": st.column_config.TextColumn("System Prompt", width="large"),
            },
        )

        # show the save button if there are changes
        changes = st.session_state[f"prompt_editor_{search}"]

        if editor_changes.has_changes(changes):
            if st.button("Save changes", type="primary"):
                save_changes(prompt_table)
                st.success("Saved!")

st.divider()

if st.button("New prompt"):
    st.switch_page("pages/new_prompt.py")
