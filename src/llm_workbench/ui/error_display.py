from collections.abc import Sequence
from typing import Any

import streamlit as st

from llm_workbench import formatting
from llm_workbench.errors import OpenRouterRequestError

ERROR_PRESENTATION = {
    "auth": {
        "icon": "🔑",
        "title": "OpenRouter authentication failed",
    },
    "credits": {
        "icon": "💳",
        "title": "Insufficient OpenRouter credits",
    },
    "rate_limit": {
        "icon": "⏳",
        "title": "OpenRouter rate limit reached",
    },
    "network": {
        "icon": "🌐",
        "title": "Network request failed",
    },
    "temporary": {
        "icon": "🛠️",
        "title": "Request temporarily failed",
    },
    "request": {
        "icon": "⚠️",
        "title": "Request rejected",
    },
    "not_found": {
        "icon": "🔎",
        "title": "Requested resource not found",
    },
    "unexpected": {
        "icon": "❗",
        "title": "Unexpected request error",
    },
}


def display_error(
    error: Exception,
    canvas: Any = st,
    context: str | None = None,
) -> None:
    if isinstance(error, OpenRouterRequestError):
        presentation = ERROR_PRESENTATION.get(
            error.kind,
            ERROR_PRESENTATION["unexpected"],
        )
        message = str(error)
    else:
        presentation = {
            "icon": "⚠️",
            "title": "Operation could not be completed",
        }
        message = str(error)

    details = canvas.expander(
        f"**:red[{presentation['title']}]**",
        icon=presentation["icon"],
        type="compact",
    )

    if context:
        details.markdown(f":grey[{context}]")

    details.caption(message)


def display_interaction_errors(
    succeeded_interactions: int,
    interaction_errors: Sequence[Exception],
    canvas: Any = st,
) -> None:
    canvas.warning(
        f"Only {formatting.pluralize(succeeded_interactions, 'response')} received. "
        f"The other requests failed with the following errors:"
    )
    for interaction_error in interaction_errors:
        display_error(
            error=interaction_error,
            canvas=canvas,
        )


def display_failed_judgments_information(
    failed_judgments,
    canvas: Any = st,
) -> None:
    canvas.error(
        f"{len(failed_judgments)} judge evaluation{'s' if len(failed_judgments) != 1 else ''} could not be completed:"
    )
    for failed_judgment in failed_judgments:
        display_error(
            error=failed_judgment["error"],
            canvas=canvas,
            context=f"Response `{failed_judgment['interaction_id']}` · judge `{failed_judgment['judge_model']}`",
        )
