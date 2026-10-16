from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st
from openrouter import operations

from llm_workbench.llm import openrouter_api
from llm_workbench.errors import OpenRouterRequestError
from llm_workbench.ui import error_display


# short TTL so credits and usage stay reasonably fresh after runs
@st.cache_data(ttl="1m", show_spinner=False)
def get_key_metadata() -> operations.GetCurrentKeyData:
    return openrouter_api.get_key_metadata()


@st.cache_data(ttl="1m", show_spinner=False)
def get_credits() -> operations.GetCreditsData:
    return openrouter_api.get_credits()


def api_key_details(canvas: Any = st.sidebar) -> None:
    canvas.subheader("OpenRouter Details")

    # check if the api key can be authentified
    with canvas.spinner(text="Fetching account information…"):
        # get key metadata
        try:
            metadata = get_key_metadata()
        except OpenRouterRequestError as error:
            error_display.display_error(error, canvas, context="Could not fetch API key information.")
            return

        # get credits
        try:
            credits = get_credits()
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
