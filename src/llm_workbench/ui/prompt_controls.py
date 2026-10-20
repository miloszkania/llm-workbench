import streamlit as st

from llm_workbench import formatting, records


def format_prompt_option(prompt_row) -> str:
    # untitled prompts are shown by the beginning of their text
    return formatting.format_prompt_label(
        prompt_row["id"],
        prompt_row["title"] or formatting.format_text_preview(prompt_row["prompt"]),
    )


def save_prompt_button(
    prompt: str,
    system_prompt: str | None,
    categories: list[str],
) -> None:
    if st.button("Save prompt", type="secondary"):
        if not formatting.normalize_prompt_text(prompt):
            st.error("The prompt cannot be empty!")
        else:
            prompt_id = records.save_prompt(prompt, system_prompt, categories)
            st.success(f"Saved as prompt #{prompt_id}")
