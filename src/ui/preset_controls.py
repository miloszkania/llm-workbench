import pandas as pd
import streamlit as st

from src import records


def save_preset_button(
        prompt: str,
        system_prompt: str | None,
        categories: list[str],
) -> None:
    if st.button("Add preset", type="secondary"):
        if not prompt:
            st.error("You need to enter the prompt!")
        else:
            preset_id = records.add_preset(system_prompt, prompt, categories)
            st.success(f"Saved as preset #{preset_id}")


def preset_table_preview(preset_table: pd.DataFrame | None = None) -> None:
    with st.spinner("Getting preset data…"):
        if preset_table is None:
            preset_table = records.get_all_presets()

    with st.expander("All presets"):
        if not preset_table.empty:
            st.dataframe(
                preset_table,
                height="content" if len(preset_table) <= 20 else 750,
                hide_index=True,

                column_order=[
                    "id",
                    "categories",
                    "prompt",
                    "system_prompt",
                ],

                column_config={
                    "id": st.column_config.TextColumn(
                        "ID",
                    ),
                    "prompt": st.column_config.TextColumn(
                        "Prompt",
                        width="large",
                    ),
                    "system_prompt": st.column_config.TextColumn(
                        "System Prompt",
                        width="large",
                    ),
                    "categories": st.column_config.MultiselectColumn(
                        "Categories",
                    ),
                },
            )
        else:
            st.warning("There are no presets yet.")
