from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src import openrouter_api, records
from src.errors import OpenRouterRequestError
from src.ui import error_display


def batch_ids_picker(
        history_table: pd.DataFrame | None = None,
        canvas: Any = st,
) -> None:
    if history_table is None:
        history_table = records.get_all_interactions()

    if history_table.empty:
        return

    canvas.subheader("Show experiment results")

    details_prompt_id = canvas.multiselect(
        "Prompt IDs",
        placeholder="Select one or more IDs",
        options=history_table["id"],
        accept_new_options=True,
    )

    if details_prompt_id is not None:
        if canvas.button("Go"):
            param_string = ",".join(map(str, details_prompt_id))
            st.switch_page("pages/experiment_results.py", query_params={"id": param_string})

    canvas.divider()


def api_key_details(canvas: Any = st.sidebar) -> None:
    canvas.subheader("OpenRouter Details")

    # check if the api key can be authentified
    with canvas.spinner(text="Fetching account information…"):
        # get key metadata
        try:
            metadata = openrouter_api.get_key_metadata()
        except OpenRouterRequestError as error:
            error_display.display_error(error, canvas, context="Could not fetch API key information.")
            return

        # get credits
        try:
            credits = openrouter_api.get_credits()
        except OpenRouterRequestError as error:
            error_display.display_error(error, canvas, context="Could not fetch credit information.")
            return

    # key label
    canvas.write(f"**API Key:** 🟢 `{metadata.label}`")

    # key expiration
    if metadata.expires_at:
        local_expiration_date = metadata.expires_at.astimezone(datetime.now().astimezone().tzinfo)

        # check if the key expires in less than 24 hours
        if metadata.expires_at - datetime.now(ZoneInfo("UTC")) < timedelta(days=1):
            canvas.write(f"**Expires at:** ⚠️ {local_expiration_date.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            canvas.write(f"**Expires at:** {local_expiration_date.strftime('%Y-%m-%d %H:%M:%S')}")

    # credits
    remaining_credits = credits.total_credits - credits.total_usage
    canvas.write(f"**Remaining credits:** ${remaining_credits:.4f}")

    canvas.space("xxsmall")

    # key limit
    if metadata.limit:
        canvas.progress(metadata.limit_remaining / metadata.limit)
        canvas.write(f"**Credit limit:** ${metadata.limit_remaining:.4f} / ${metadata.limit:.4f} remaining")

        canvas.space("xxsmall")

    # usage
    canvas.write(f"**Daily usage:** ${metadata.usage_daily:.4f}")
    canvas.write(f"**Weekly usage:** ${metadata.usage_weekly:.4f}")
    canvas.write(f"**Monthly usage:** ${metadata.usage_monthly:.4f}")
